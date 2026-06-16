# src/enrichers.py
"""Enrichment layer: fetch HTML, detect pixels, detect platform, PageSpeed.

ARSITEKTUR:
- fetch_site() dengan multi-strategy fallback (https -> http -> www)
- detect_pixels() dari HTML markup (regex-based, fast)
- detect_platform() dari HTML/header signals
- fetch_pagespeed() via Google PageSpeed Insights API
- enrich_domain() = orchestrator concurrent semua di atas
- enrich_all() = batch dengan semaphore (rate-limit aware)

PRINSIP:
- Graceful degradation: 1 enricher fail != domain di-discard
- Verbose logging: tiap fail wajib ada reason
- Concurrent-safe: semaphore + per-API rate limit
- Output detection_notes dalam Bahasa Indonesia
- Tier-aware: tier 1 brand → confidence boost untuk pixel detection
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

import httpx

from src.config import PAGESPEED_API_KEY
from src.models import EnrichmentResult


# ============================================================
# Constants
# ============================================================
_USER_AGENT = (
    "Mozilla/5.0 (compatible; ApexResearchBot/1.0; "
    "+https://github.com/idincode/idincode-researche)"
)

_DEFAULT_TIMEOUT = 15.0
_PAGESPEED_TIMEOUT = 60.0
_MAX_CONCURRENT_ENRICHMENTS = 8
_MAX_CONCURRENT_PAGESPEED = 4

_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_JS_FRAMEWORK_HINTS = (
    "__next",
    "_next/static",
    "__nuxt",
    "webpack",
    "vite",
    "react",
    "hydration",
    "window.__initial_state__",
    "window.__nuxt__",
    "defer",
    'type="module"',
)

_FASHION_HINTS = (
    "fashion",
    "apparel",
    "footwear",
    "streetwear",
    "batik",
    "hijab",
    "collection",
    "lookbook",
    "shop now",
    "cart",
    "checkout",
    "keranjang",
    "pakaian",
    "baju",
    "sepatu",
)

_SKINCARE_HINTS = (
    "skincare",
    "skin care",
    "beauty",
    "kosmetik",
    "cosmetic",
    "serum",
    "moisturizer",
    "sunscreen",
    "kecantikan",
    "wajah",
)

# ============================================================
# Public API
# ============================================================
async def enrich_all(targets: list[dict]) -> list[EnrichmentResult]:
    """Enrich SEMUA targets concurrent dengan semaphore."""
    if not targets:
        return []

    print(f"[pipeline] Enriching {len(targets)} targets concurrently...")
    sem = asyncio.Semaphore(_MAX_CONCURRENT_ENRICHMENTS)

    async def _bounded(target: dict) -> EnrichmentResult:
        async with sem:
            return await enrich_domain(target)

    results = await asyncio.gather(
        *[_bounded(t) for t in targets],
        return_exceptions=False,
    )

    reachable = sum(1 for r in results if r.reachable)
    print(f"[pipeline] Enrichment done. Reachable: {reachable}/{len(results)}")

    return list(results)


async def enrich_domain(target: dict) -> EnrichmentResult:
    """Enrich single domain. Robust to all failure modes."""
    domain = (
        target["domain"]
        .strip()
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .rstrip("/")
    )
    location = target.get("location")
    niche = target.get("niche", "default")
    category = target.get("category")
    brand = target.get("brand")
    tier = target.get("tier")
    notes = target.get("notes")

    print(f"[enrich] -> {domain}")

    html, response_ms, final_url, status_code, fail_reason = await _fetch_site_with_fallback(domain)

    if html is None:
        print(f"[enrich] FAILED {domain} UNREACHABLE: {fail_reason}")
        return EnrichmentResult(
            domain=domain,
            location=location,
            niche=niche,
            category=category,
            brand=brand,
            tier=tier,
            notes=notes,
            reachable=False,
            fail_reason=fail_reason,
            response_ms=response_ms,
            status_code=status_code,
            platform=None,
            has_meta_pixel=False,
            has_tiktok_pixel=False,
            has_ga4=False,
            has_gtm=False,
            has_google_ads=False,
            pixel_detection_method="html_regex",
            pixel_confidence="low",
            firmographics_confidence="low",
            data_confidence="low",
            firmographics_source="free_enrichment",
            detection_notes=(
                "Domain tidak bisa diakses. Verifikasi pixel dan firmografi tidak memungkinkan. "
                "Cek manual apakah website sedang down atau memang sudah tidak aktif."
            ),
            data_quality_flags=[
                "unreachable",
                "pixel_detection_unavailable",
                "firmographics_unavailable",
            ],
            pagespeed_score=None,
            lcp_ms=None,
        )

    pixels = _detect_pixels(html)
    platform = _detect_platform(html)
    pixel_confidence, pixel_flags = _infer_pixel_confidence(
        html=html,
        niche=niche,
        category=category,
        platform=platform,
        pixels=pixels,
        tier=tier,
        brand=brand,
    )
    pixel_notes = _build_pixel_detection_notes(
        pixel_confidence=pixel_confidence,
        tier=tier,
        brand=brand,
    )

    pagespeed_score, lcp_ms = await _fetch_pagespeed(domain)

    print(
        f"[enrich] OK {domain} | platform={platform or 'unknown'} | "
        f"pixels={sum(pixels.values())}/5 | ps={pagespeed_score} | "
        f"lcp={lcp_ms}ms | rt={response_ms}ms | "
        f"url={final_url or 'n/a'} | pixel_conf={pixel_confidence}"
    )

    return EnrichmentResult(
        domain=domain,
        location=location,
        niche=niche,
        category=category,
        brand=brand,
        tier=tier,
        notes=notes,
        reachable=True,
        fail_reason=None,
        response_ms=response_ms,
        status_code=status_code,
        platform=platform,
        has_meta_pixel=pixels["meta"],
        has_tiktok_pixel=pixels["tiktok"],
        has_ga4=pixels["ga4"],
        has_gtm=pixels["gtm"],
        has_google_ads=pixels["google_ads"],
        pixel_detection_method="html_regex",
        pixel_confidence=pixel_confidence,
        firmographics_confidence="low",  # akan di-update di bi_enrich step
        data_confidence=pixel_confidence,
        firmographics_source="free_enrichment",
        detection_notes=pixel_notes,
        data_quality_flags=pixel_flags,
        pagespeed_score=pagespeed_score,
        lcp_ms=lcp_ms,
        raw_html=html,
    )


# ============================================================
# Fetch with multi-strategy fallback
# ============================================================
async def _fetch_site_with_fallback(
    domain: str,
) -> tuple[Optional[str], Optional[int], Optional[str], Optional[int], Optional[str]]:
    """Try multiple URL variants. Return (html, response_ms, final_url, status, fail_reason)."""
    if domain.startswith("www."):
        bare = domain[4:]
        variants = [
            f"https://{domain}",
            f"https://{bare}",
            f"http://{domain}",
            f"http://{bare}",
        ]
    else:
        variants = [
            f"https://{domain}",
            f"https://www.{domain}",
            f"http://{domain}",
            f"http://www.{domain}",
        ]

    last_fail_reason: Optional[str] = None
    last_status: Optional[int] = None
    last_response_ms: Optional[int] = None

    for url in variants:
        html, response_ms, status, fail_reason = await _fetch_once(url)
        if html is not None:
            return html, response_ms, url, status, None

        last_fail_reason = fail_reason
        last_status = status
        last_response_ms = response_ms

    return None, last_response_ms, None, last_status, last_fail_reason


async def _fetch_once(
    url: str,
) -> tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    """Single GET request. Return (html, response_ms, status_code, fail_reason)."""
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers=_HEADERS,
            verify=True,
        ) as client:
            resp = await client.get(url)
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "").lower()
                if "html" not in content_type and "text" not in content_type:
                    return None, elapsed_ms, resp.status_code, f"non-html content-type: {content_type}"

                text = resp.text
                if len(text) > 5_000_000:
                    text = text[:5_000_000]
                return text, elapsed_ms, resp.status_code, None

            return None, elapsed_ms, resp.status_code, f"HTTP {resp.status_code}"

    except httpx.ConnectTimeout:
        return None, None, None, "connect_timeout"
    except httpx.ReadTimeout:
        return None, None, None, "read_timeout"
    except httpx.ConnectError as e:
        msg = str(e)[:100]
        return None, None, None, f"connect_error: {msg}"
    except httpx.RemoteProtocolError as e:
        return None, None, None, f"protocol_error: {str(e)[:80]}"
    except httpx.TooManyRedirects:
        return None, None, None, "too_many_redirects"
    except httpx.UnsupportedProtocol as e:
        return None, None, None, f"unsupported_protocol: {str(e)[:80]}"
    except (httpx.HTTPError, ssl_error_catch()) as e:  # type: ignore
        return None, None, None, f"http_error: {type(e).__name__}: {str(e)[:80]}"
    except Exception as e:  # noqa: BLE001
        return None, None, None, f"unknown: {type(e).__name__}: {str(e)[:80]}"


def ssl_error_catch():
    """Lazy import ssl to add to exception tuple."""
    try:
        import ssl
        return ssl.SSLError
    except ImportError:
        return Exception


# ============================================================
# Pixel detection
# ============================================================
_META_PIXEL_PATTERNS = [
    re.compile(r"connect\.facebook\.net/[^/]+/fbevents\.js", re.IGNORECASE),
    re.compile(r"fbq\s*\(\s*['\"]init['\"]", re.IGNORECASE),
    re.compile(r"facebook-pixel", re.IGNORECASE),
]

_TIKTOK_PIXEL_PATTERNS = [
    re.compile(r"analytics\.tiktok\.com/i18n/pixel", re.IGNORECASE),
    re.compile(r"ttq\.load\s*\(", re.IGNORECASE),
    re.compile(r"tiktok-pixel", re.IGNORECASE),
]

_GA4_PATTERNS = [
    re.compile(r"www\.googletagmanager\.com/gtag/js\?id=G-[A-Z0-9]+", re.IGNORECASE),
    re.compile(r"gtag\s*\(\s*['\"]config['\"]\s*,\s*['\"]G-", re.IGNORECASE),
]

_GTM_PATTERNS = [
    re.compile(r"www\.googletagmanager\.com/gtm\.js\?id=GTM-", re.IGNORECASE),
    re.compile(r"GTM-[A-Z0-9]{4,}", re.IGNORECASE),
]

_GOOGLE_ADS_PATTERNS = [
    re.compile(r"www\.googletagmanager\.com/gtag/js\?id=AW-", re.IGNORECASE),
    re.compile(r"gtag\s*\(\s*['\"]config['\"]\s*,\s*['\"]AW-", re.IGNORECASE),
    re.compile(r"google_conversion_id", re.IGNORECASE),
]


def _detect_pixels(html: str) -> dict[str, bool]:
    return {
        "meta": _any_match(html, _META_PIXEL_PATTERNS),
        "tiktok": _any_match(html, _TIKTOK_PIXEL_PATTERNS),
        "ga4": _any_match(html, _GA4_PATTERNS),
        "gtm": _any_match(html, _GTM_PATTERNS),
        "google_ads": _any_match(html, _GOOGLE_ADS_PATTERNS),
    }


def _any_match(html: str, patterns: list[re.Pattern]) -> bool:
    return any(pattern.search(html) for pattern in patterns)


def _infer_pixel_confidence(
    *,
    html: str,
    niche: str | None,
    category: str | None,
    platform: str | None,
    pixels: dict[str, bool],
    tier: Optional[int] = None,
    brand: Optional[str] = None,
) -> tuple[str, list[str]]:
    """Infer pixel detection confidence dengan awareness terhadap tier &amp; brand."""
    flags: list[str] = ["pixel_detection_regex_only"]

    found_count = sum(1 for value in pixels.values() if value)
    html_low = html.lower()
    js_heavy = any(hint in html_low for hint in _JS_FRAMEWORK_HINTS)
    retail_like = (
        _is_fashion_like_text(f"{niche or ''} {category or ''} {html_low[:2000]}")
        or _is_skincare_like_text(f"{niche or ''} {category or ''} {html_low[:2000]}")
    )
    ecommerce_like = platform in {"shopify", "woocommerce", "bigcommerce"}

    if found_count >= 3:
        if js_heavy:
            flags.append("js_rendered_site_partial_visibility")
            return "medium", flags
        return "high", flags

    if found_count >= 1:
        flags.append("partial_pixel_visibility")
        if js_heavy:
            flags.append("possible_additional_js_loaded_pixels")
        return "medium", flags

    flags.append("pixels_not_detected_in_html")
    if js_heavy:
        flags.append("possible_js_loaded_pixels")
    if retail_like or ecommerce_like:
        flags.append("high_false_negative_risk_for_pixels")
    if tier == 1 and brand:
        # Brand tier 1 dengan budget iklan besar — hampir pasti punya pixel via GTM
        flags.append("tier1_brand_likely_uses_gtm_async_loading")
    return "low", flags


def _build_pixel_detection_notes(
    *,
    pixel_confidence: str,
    tier: Optional[int] = None,
    brand: Optional[str] = None,
) -> str:
    """Build pixel detection notes dalam Bahasa Indonesia."""
    notes = [
        "Deteksi pixel pakai regex HTML statis (tag yang di-load via JavaScript bisa tidak terlihat).",
    ]
    if pixel_confidence == "low":
        notes.append(
            "Pixel tidak terdeteksi — perlakukan sebagai 'belum terverifikasi', bukan 'tidak ada'."
        )
        if tier == 1 and brand:
            notes.append(
                f"Catatan: {brand} adalah brand tier 1 yang biasanya aktif iklan besar — "
                "hampir pasti pixel terpasang via GTM async, perlu konfirmasi via browser DevTools."
            )
    elif pixel_confidence == "medium":
        notes.append("Stack tracking terdeteksi sebagian — kemungkinan ada pixel tambahan yang di-load async.")
    else:
        notes.append("Stack tracking terdeteksi dengan visibility yang baik.")
    return " ".join(notes)


def _is_fashion_like_text(text: str) -> bool:
    low = text.lower()
    return any(keyword in low for keyword in _FASHION_HINTS)


def _is_skincare_like_text(text: str) -> bool:
    low = text.lower()
    return any(keyword in low for keyword in _SKINCARE_HINTS)


# ============================================================
# Platform detection
# ============================================================
_PLATFORM_SIGNALS: list[tuple[str, list[re.Pattern]]] = [
    (
        "shopify",
        [
            re.compile(r"cdn\.shopify\.com", re.IGNORECASE),
            re.compile(r"shopify\.theme", re.IGNORECASE),
            re.compile(r"Shopify\.shop", re.IGNORECASE),
        ],
    ),
    (
        "woocommerce",
        [
            re.compile(r"woocommerce", re.IGNORECASE),
            re.compile(r"wc-blocks", re.IGNORECASE),
        ],
    ),
    (
        "wordpress",
        [
            re.compile(r"wp-content/", re.IGNORECASE),
            re.compile(r"wp-includes/", re.IGNORECASE),
            re.compile(r"wp-json/", re.IGNORECASE),
        ],
    ),
    (
        "wix",
        [
            re.compile(r"static\.wixstatic\.com", re.IGNORECASE),
            re.compile(r"_wixCIDX", re.IGNORECASE),
        ],
    ),
    (
        "squarespace",
        [
            re.compile(r"squarespace\.com", re.IGNORECASE),
            re.compile(r"static1\.squarespace\.com", re.IGNORECASE),
        ],
    ),
    (
        "webflow",
        [
            re.compile(r"webflow\.com", re.IGNORECASE),
            re.compile(r"data-wf-page", re.IGNORECASE),
        ],
    ),
    (
        "bigcommerce",
        [
            re.compile(r"cdn\.bcapp\.dev", re.IGNORECASE),
            re.compile(r"bigcommerce\.com", re.IGNORECASE),
        ],
    ),
    (
        "duda",
        [
            re.compile(r"irp\.cdn-website\.com", re.IGNORECASE),
            re.compile(r"dudamobile", re.IGNORECASE),
        ],
    ),
]


def _detect_platform(html: str) -> Optional[str]:
    for platform_name, patterns in _PLATFORM_SIGNALS:
        if any(pattern.search(html) for pattern in patterns):
            return platform_name
    return None


# ============================================================
# PageSpeed
# ============================================================
_PAGESPEED_SEM = asyncio.Semaphore(_MAX_CONCURRENT_PAGESPEED)


async def _fetch_pagespeed(domain: str) -> tuple[Optional[int], Optional[int]]:
    """Fetch PageSpeed mobile score + LCP. Return (score, lcp_ms)."""
    if not PAGESPEED_API_KEY:
        return None, None

    url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": f"https://{domain}",
        "strategy": "mobile",
        "category": "performance",
        "key": PAGESPEED_API_KEY,
    }

    async with _PAGESPEED_SEM:
        try:
            async with httpx.AsyncClient(timeout=_PAGESPEED_TIMEOUT) as client:
                resp = await client.get(url, params=params)

                if resp.status_code != 200:
                    print(f"[pagespeed] {domain}: HTTP {resp.status_code}")
                    return None, None

                data = resp.json()
                lighthouse = data.get("lighthouseResult", {})
                categories = lighthouse.get("categories", {})
                perf = categories.get("performance", {})
                score = perf.get("score")
                score_int = int(score * 100) if isinstance(score, (int, float)) else None

                audits = lighthouse.get("audits", {})
                lcp_audit = audits.get("largest-contentful-paint", {})
                lcp_ms = lcp_audit.get("numericValue")
                lcp_int = int(lcp_ms) if isinstance(lcp_ms, (int, float)) else None

                return score_int, lcp_int

        except httpx.TimeoutException:
            print(f"[pagespeed] {domain}: timeout")
            return None, None
        except Exception as e:  # noqa: BLE001
            print(f"[pagespeed] {domain}: {type(e).__name__}: {str(e)[:80]}")
            return None, None