from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urljoin

import httpx

from src.business_models import BusinessIntelLead, BusinessIntelTarget

MARKETPLACE_PATTERNS: dict[str, re.Pattern[str]] = {
    "Shopee": re.compile(r"shopee\.(co\.id|com)", re.IGNORECASE),
    "TikTok Shop": re.compile(r"tiktok\.com/(?:@|shop|view)|shop\.tiktok\.com", re.IGNORECASE),
    "Tokopedia": re.compile(r"tokopedia\.com", re.IGNORECASE),
    "Lazada": re.compile(r"lazada\.(co\.id|com)", re.IGNORECASE),
    "Blibli": re.compile(r"blibli\.com", re.IGNORECASE),
    "Zalora": re.compile(r"zalora\.(co\.id|com)", re.IGNORECASE),
}

PAYMENT_KEYWORDS = {
    "midtrans": "Midtrans",
    "xendit": "Xendit",
    "duitku": "Duitku",
    "ipaymu": "iPaymu",
    "doku": "DOKU",
    "gopay": "GoPay",
    "ovo": "OVO",
    "dana": "DANA",
    "shopeepay": "ShopeePay",
    "linkaja": "LinkAja",
    "bca virtual account": "BCA Virtual Account",
    "virtual account": "Virtual Account",
    "credit card": "Credit Card",
    "bank transfer": "Bank Transfer",
    "cod": "COD",
    "qris": "QRIS",
}

CHECKOUT_PATTERNS = [
    r"checkout",
    r"keranjang",
    r"cart",
    r"bayar",
    r"proceed to checkout",
    r"lanjutkan pembayaran",
]

PROMO_PATTERNS = [
    r"promo code",
    r"voucher",
    r"kode promo",
    r"coupon",
    r"kupon",
    r"diskon tambahan",
]

WHATSAPP_PATTERNS = [r"wa\.me/", r"whatsapp\.com", r"konsultasi via whatsapp", r"chat admin"]


@dataclass(slots=True)
class FetchResult:
    final_url: str
    status_code: int
    html: str
    fetch_status: str


class WebsiteFetcher:
    def __init__(self, timeout_seconds: float, user_agent: str):
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        self.client = httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=headers)

    async def close(self) -> None:
        await self.client.aclose()

    async def fetch(self, domain: str) -> FetchResult:
        candidates = [f"https://{domain}", f"http://{domain}"]
        last_error = "unreachable"
        for url in candidates:
            try:
                response = await self.client.get(url)
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and response.text:
                    html = response.text
                else:
                    html = response.text
                return FetchResult(
                    final_url=str(response.url),
                    status_code=response.status_code,
                    html=html,
                    fetch_status="ok" if response.is_success else f"http_{response.status_code}",
                )
            except httpx.TimeoutException:
                last_error = "timeout"
            except httpx.HTTPError:
                last_error = "http_error"
        return FetchResult(final_url="", status_code=0, html="", fetch_status=last_error)


class AdIntelProvider:
    name = "none"

    async def fetch(self, target: BusinessIntelTarget, competitors: list[str]) -> dict[str, Any]:
        return {
            "provider": self.name,
            "meta_ads_count": 0,
            "tiktok_ads_count": 0,
            "confidence": "low",
            "flags": ["ad_provider_not_configured"],
            "notes": "Provider iklan belum dikonfigurasi.",
        }


class EnvJsonAdIntelProvider(AdIntelProvider):
    name = "env_json_endpoint"

    def __init__(self, timeout_seconds: float, user_agent: str):
        self.api_url = (httpx.URL("https://example.invalid") if False else None)
        self.endpoint = ""
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        import os

        self.endpoint = os.getenv("BUSINESS_INTEL_AD_API_URL", "").strip()
        self.api_key = os.getenv("BUSINESS_INTEL_AD_API_KEY", "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint)

    async def fetch(self, target: BusinessIntelTarget, competitors: list[str]) -> dict[str, Any]:
        if not self.enabled:
            return await super().fetch(target, competitors)

        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key

        payload = {
            "domain": target.domain,
            "brand": target.brand,
            "niche": target.niche,
            "category": target.category,
            "competitors": competitors,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
            try:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, json.JSONDecodeError):
                return {
                    "provider": self.name,
                    "meta_ads_count": 0,
                    "tiktok_ads_count": 0,
                    "confidence": "low",
                    "flags": ["ad_provider_request_failed"],
                    "notes": "Provider iklan gagal merespons JSON yang valid.",
                }

        return {
            "provider": self.name,
            "meta_ads_count": _safe_int(data.get("meta_ads_count")),
            "tiktok_ads_count": _safe_int(data.get("tiktok_ads_count")),
            "confidence": str(data.get("confidence", "medium")).lower(),
            "flags": _ensure_list(data.get("flags")),
            "notes": str(data.get("notes", "Data iklan berasal dari provider eksternal.")).strip(),
        }


class BusinessIntelResearcher:
    def __init__(self, timeout_seconds: float, user_agent: str):
        self.fetcher = WebsiteFetcher(timeout_seconds=timeout_seconds, user_agent=user_agent)
        self.ad_provider = EnvJsonAdIntelProvider(
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
        )

    async def close(self) -> None:
        await self.fetcher.close()

    async def research(self, target: BusinessIntelTarget, competitors: list[str]) -> BusinessIntelLead:
        fetch_result = await self.fetcher.fetch(target.domain)
        html = fetch_result.html
        lower_html = html.lower()
        marketplace_matches = detect_marketplaces(html)
        payment_methods = detect_payment_methods(lower_html)
        checkout_detected = detect_any(lower_html, CHECKOUT_PATTERNS)
        cart_detected = detect_any(lower_html, [r"add to cart", r"keranjang", r"cart-drawer", r"mini-cart"])
        promo_detected = detect_any(lower_html, PROMO_PATTERNS)
        voucher_detected = detect_any(lower_html, [r"voucher", r"kode voucher", r"coupon", r"kupon"])
        whatsapp_detected = detect_any(lower_html, WHATSAPP_PATTERNS)
        ad_intel = await self.ad_provider.fetch(target, competitors)

        funnel_health_score, funnel_gaps = compute_funnel_health(
            checkout_detected=checkout_detected,
            cart_detected=cart_detected,
            payment_methods=payment_methods,
            promo_detected=promo_detected,
            whatsapp_detected=whatsapp_detected,
            marketplaces=marketplace_matches,
        )
        ad_dominance_score = compute_ad_dominance_score(
            ad_intel.get("meta_ads_count", 0),
            ad_intel.get("tiktok_ads_count", 0),
            ad_intel.get("confidence", "low"),
        )
        business_score = compute_business_score(
            tier=target.tier,
            funnel_health_score=funnel_health_score,
            ad_dominance_score=ad_dominance_score,
            marketplace_count=len(marketplace_matches),
            promo_detected=promo_detected,
            confidence=ad_intel.get("confidence", "low"),
        )

        priority = classify_priority(business_score)
        opportunities = build_business_opportunities(
            target=target,
            funnel_health_score=funnel_health_score,
            funnel_gaps=funnel_gaps,
            marketplaces=marketplace_matches,
            ad_intel=ad_intel,
            promo_detected=promo_detected,
        )
        outreach_angle = build_outreach_angle(target, business_score, funnel_health_score, ad_intel)
        summary = build_executive_summary(
            target=target,
            funnel_health_score=funnel_health_score,
            marketplaces=marketplace_matches,
            ad_intel=ad_intel,
            fetch_status=fetch_result.fetch_status,
        )
        flags = build_quality_flags(fetch_result.fetch_status, marketplace_matches, payment_methods, ad_intel)
        notes = build_detection_notes(fetch_result.fetch_status, ad_intel)
        confidence = derive_data_confidence(fetch_result.fetch_status, payment_methods, marketplace_matches, ad_intel)

        return BusinessIntelLead(
            domain=target.domain,
            brand=target.brand,
            tier=target.tier,
            location=target.location,
            niche=target.niche,
            category=target.category,
            notes=target.notes,
            business_score=business_score,
            business_priority=priority,
            data_confidence=confidence,
            fetch_status=fetch_result.fetch_status,
            final_url=fetch_result.final_url,
            website_status_code=fetch_result.status_code,
            marketplace_presence="ya" if marketplace_matches else "tidak",
            marketplace_count=len(marketplace_matches),
            marketplaces=", ".join(marketplace_matches),
            shopee_link_found=yes_no("Shopee" in marketplace_matches),
            tiktok_shop_link_found=yes_no("TikTok Shop" in marketplace_matches),
            tokopedia_link_found=yes_no("Tokopedia" in marketplace_matches),
            lazada_link_found=yes_no("Lazada" in marketplace_matches),
            blibli_link_found=yes_no("Blibli" in marketplace_matches),
            zalora_link_found=yes_no("Zalora" in marketplace_matches),
            checkout_detected=yes_no(checkout_detected),
            cart_detected=yes_no(cart_detected),
            payment_options_detected=yes_no(bool(payment_methods)),
            payment_methods=", ".join(payment_methods),
            promo_code_box_detected=yes_no(promo_detected),
            voucher_signal_detected=yes_no(voucher_detected),
            whatsapp_checkout_signal=yes_no(whatsapp_detected),
            funnel_health_score=funnel_health_score,
            funnel_gaps="; ".join(funnel_gaps),
            ad_provider=str(ad_intel.get("provider", "none")),
            meta_ads_count=_safe_int(ad_intel.get("meta_ads_count")),
            tiktok_ads_count=_safe_int(ad_intel.get("tiktok_ads_count")),
            ad_dominance_score=ad_dominance_score,
            ad_intel_confidence=str(ad_intel.get("confidence", "low")).upper(),
            competitor_1=competitors[0] if len(competitors) > 0 else "",
            competitor_2=competitors[1] if len(competitors) > 1 else "",
            competitor_3=competitors[2] if len(competitors) > 2 else "",
            competitor_set=", ".join(competitors),
            business_opportunities=opportunities,
            outreach_angle=outreach_angle,
            executive_summary=summary,
            detection_notes=notes,
            data_quality_flags=", ".join(flags),
            raw_signals={
                "html_length": len(html),
                "payment_methods": payment_methods,
                "marketplaces": marketplace_matches,
                "ad_intel": ad_intel,
            },
        )


def detect_marketplaces(html: str) -> list[str]:
    matches: list[str] = []
    decoded = unescape(html)
    for name, pattern in MARKETPLACE_PATTERNS.items():
        if pattern.search(decoded):
            matches.append(name)
    return matches


def detect_payment_methods(lower_html: str) -> list[str]:
    methods: list[str] = []
    for keyword, label in PAYMENT_KEYWORDS.items():
        if keyword in lower_html and label not in methods:
            methods.append(label)
    return methods


def detect_any(lower_html: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, lower_html, re.IGNORECASE) for pattern in patterns)


def compute_funnel_health(
    *,
    checkout_detected: bool,
    cart_detected: bool,
    payment_methods: list[str],
    promo_detected: bool,
    whatsapp_detected: bool,
    marketplaces: list[str],
) -> tuple[int, list[str]]:
    score = 35
    gaps: list[str] = []

    if checkout_detected:
        score += 18
    else:
        gaps.append("Checkout tidak terdeteksi jelas di HTML publik")

    if cart_detected:
        score += 10
    else:
        gaps.append("Signal cart/keranjang lemah atau tidak terlihat")

    if payment_methods:
        score += min(20, len(payment_methods) * 4)
    else:
        gaps.append("Metode pembayaran tidak terlihat dari HTML publik")

    if promo_detected:
        score += 8
    else:
        gaps.append("Kotak promo/voucher belum terdeteksi")

    if whatsapp_detected:
        score += 5

    if marketplaces:
        score -= min(16, len(marketplaces) * 4)
        gaps.append("Ada indikasi funnel diarahkan ke marketplace pihak ketiga")

    return max(0, min(score, 100)), gaps


def compute_ad_dominance_score(meta_ads_count: int, tiktok_ads_count: int, confidence: str) -> int:
    total = max(0, meta_ads_count) + max(0, tiktok_ads_count)
    if total == 0:
        base = 20
    elif total <= 10:
        base = 45
    elif total <= 40:
        base = 65
    elif total <= 100:
        base = 82
    else:
        base = 92

    normalized_confidence = confidence.lower()
    if normalized_confidence == "low":
        base -= 8
    elif normalized_confidence == "medium":
        base -= 3
    return max(0, min(base, 100))


def compute_business_score(
    *,
    tier: int,
    funnel_health_score: int,
    ad_dominance_score: int,
    marketplace_count: int,
    promo_detected: bool,
    confidence: str,
) -> int:
    score = 50
    score += max(0, 70 - funnel_health_score) // 2
    score += ad_dominance_score // 5
    score += min(10, marketplace_count * 3)
    if not promo_detected:
        score += 4
    if tier == 2:
        score += 6
    elif tier == 3:
        score += 10

    normalized_confidence = confidence.lower()
    if normalized_confidence == "low":
        score -= 5
    elif normalized_confidence == "medium":
        score -= 2
    return max(0, min(score, 100))


def classify_priority(score: int) -> str:
    if score >= 85:
        return "premium_gold"
    if score >= 70:
        return "pro"
    if score >= 55:
        return "starter"
    return "all"


def build_business_opportunities(
    *,
    target: BusinessIntelTarget,
    funnel_health_score: int,
    funnel_gaps: list[str],
    marketplaces: list[str],
    ad_intel: dict[str, Any],
    promo_detected: bool,
) -> str:
    parts: list[str] = []
    if marketplaces:
        parts.append(
            f"Brand masih menunjukkan ketergantungan ke marketplace ({', '.join(marketplaces)}), jadi ada peluang mendorong penjualan direct ke website sendiri untuk jaga margin."
        )
    if funnel_health_score < 60:
        parts.append(
            f"Funnel health baru {funnel_health_score}/100; gap utama: {'; '.join(funnel_gaps[:3])}."
        )
    if not promo_detected:
        parts.append("Signal promo/voucher tidak terlihat, padahal mekanisme ini sering dipakai untuk menutup conversion gap pada traffic berbayar.")

    total_ads = _safe_int(ad_intel.get("meta_ads_count")) + _safe_int(ad_intel.get("tiktok_ads_count"))
    if total_ads > 0:
        parts.append(
            f"Terlihat ada jejak aktivasi iklan (estimasi {total_ads} ads aktif lintas Meta/TikTok), jadi setiap friction di funnel berpotensi membakar budget lebih cepat."
        )
    else:
        parts.append("Data iklan masih terbatas; bila provider iklan diaktifkan, narasi share-of-voice bisa dibuat lebih tajam untuk owner/CMO.")

    if target.tier >= 2:
        parts.append("Brand tier scaling seperti ini biasanya lebih responsif terhadap insight yang langsung mengaitkan margin, conversion rate, dan ketergantungan marketplace.")
    return " ".join(parts)


def build_outreach_angle(
    target: BusinessIntelTarget,
    business_score: int,
    funnel_health_score: int,
    ad_intel: dict[str, Any],
) -> str:
    total_ads = _safe_int(ad_intel.get("meta_ads_count")) + _safe_int(ad_intel.get("tiktok_ads_count"))
    if total_ads > 0:
        return (
            f"Subject: Observasi funnel {target.brand or target.domain} - ada potensi budget iklan bocor saat traffic dibawa ke website"
        )
    if funnel_health_score < 60:
        return (
            f"Subject: Ada beberapa friction di funnel {target.brand or target.domain} yang berpotensi menahan konversi direct checkout"
        )
    return (
        f"Subject: Riset singkat bisnis {target.brand or target.domain} - peluang memperkuat penjualan direct tanpa terlalu bergantung marketplace"
    )


def build_executive_summary(
    *,
    target: BusinessIntelTarget,
    funnel_health_score: int,
    marketplaces: list[str],
    ad_intel: dict[str, Any],
    fetch_status: str,
) -> str:
    total_ads = _safe_int(ad_intel.get("meta_ads_count")) + _safe_int(ad_intel.get("tiktok_ads_count"))
    marketplace_text = ", ".join(marketplaces) if marketplaces else "tidak terdeteksi"
    return (
        f"{target.brand or target.domain} dianalisis untuk business-intelligence ringan dengan fokus funnel health dan ketergantungan marketplace. "
        f"Fetch status: {fetch_status}. Funnel health: {funnel_health_score}/100. "
        f"Marketplace presence: {marketplace_text}. Estimasi ad signals lintas provider: {total_ads}."
    )


def build_quality_flags(
    fetch_status: str,
    marketplaces: list[str],
    payment_methods: list[str],
    ad_intel: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    if fetch_status != "ok":
        flags.append(f"fetch_{fetch_status}")
    if marketplaces:
        flags.append("marketplace_presence_detected")
    else:
        flags.append("marketplace_presence_not_detected")
    if not payment_methods:
        flags.append("payment_methods_not_visible_in_static_html")
    flags.extend(_ensure_list(ad_intel.get("flags")))
    return flags


def build_detection_notes(fetch_status: str, ad_intel: dict[str, Any]) -> str:
    ad_notes = str(ad_intel.get("notes", "")).strip()
    parts = [
        "Website dianalisis via HTML publik tanpa eksekusi JavaScript penuh.",
        f"Fetch status: {fetch_status}.",
    ]
    if ad_notes:
        parts.append(ad_notes)
    parts.append("Deteksi funnel dan marketplace bersifat research-grade; validasi manual tetap disarankan untuk lead prioritas tinggi.")
    return " ".join(parts)


def derive_data_confidence(
    fetch_status: str,
    payment_methods: list[str],
    marketplaces: list[str],
    ad_intel: dict[str, Any],
) -> str:
    if fetch_status != "ok":
        return "low"
    score = 0
    if payment_methods:
        score += 1
    if marketplaces:
        score += 1
    confidence = str(ad_intel.get("confidence", "low")).lower()
    if confidence == "high":
        score += 2
    elif confidence == "medium":
        score += 1

    if score >= 3:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def yes_no(value: bool) -> str:
    return "ya" if value else "tidak"


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
