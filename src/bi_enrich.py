# src/bi_enrich.py
"""Business Intelligence Enrichment (zero-budget, HTML-only) — OUTPUT BAHASA INDONESIA.

Roadmap v3.7:
- Output detection_notes & bi_summary dalam Bahasa Indonesia
- Tier-aware override: kalau tier=1 di YAML, asumsikan brand established (override estimate kecil)
- Brand-name aware: kalau ada brand field, treat as verified entity (boost confidence)
- Marketplace detection: deteksi mention Shopee/TikTok Shop/Tokopedia di HTML

Output dict (semua deterministic & fail-safe):
    employee_range            : str   -> "1-10" / "11-50" / "51-200" / "201-500" / "500+" / "unknown"
    location_count            : int   -> estimasi jumlah lokasi/cabang (>=1 kalau reachable)
    founded_year              : int?  -> tahun berdiri kalau ke-detect
    years_in_business         : int?  -> turunan dari founded_year
    social_profiles           : list  -> ["facebook","instagram","linkedin",...]
    tech_signals              : list  -> ["calendly","stripe","intercom","mailchimp",...]
    marketplaces              : list  -> ["shopee","tokopedia","tiktok_shop",...]
    bi_score                  : int   -> 0-100 indeks "kematangan/sophistication" bisnis
    firmographics_confidence  : str   -> high / medium / low
    firmographics_source      : str   -> free_enrichment / tier_metadata_assisted
    detection_notes           : str   -> catatan limitasi enrichment (Bahasa Indonesia)
    data_quality_flags        : list  -> flag kualitas data
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

# ============================================================
# Social platform detection (host substring -> label)
# ============================================================
_SOCIAL_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("facebook", ("facebook.com/", "fb.com/", "fb.me/")),
    ("instagram", ("instagram.com/",)),
    ("linkedin", ("linkedin.com/company/", "linkedin.com/in/", "linkedin.com/")),
    ("youtube", ("youtube.com/", "youtu.be/")),
    ("tiktok", ("tiktok.com/@", "tiktok.com/")),
    ("twitter", ("twitter.com/", "x.com/")),
    ("pinterest", ("pinterest.com/",)),
    ("yelp", ("yelp.com/biz/", "yelp.com/")),
)

_SOCIAL_NOISE = (
    "facebook.com/sharer",
    "facebook.com/tr",
    "twitter.com/intent",
    "twitter.com/share",
    "linkedin.com/sharearticle",
    "pinterest.com/pin/create",
    "youtube.com/embed",
)

# ============================================================
# Marketplace detection (sinyal komersial khas Indonesia)
# ============================================================
_MARKETPLACE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("shopee", ("shopee.co.id/", "shopee.com/", "shp.ee/")),
    ("tokopedia", ("tokopedia.com/", "tkp.me/")),
    ("tiktok_shop", ("tiktok.com/shop", "shop.tiktok.com")),
    ("lazada", ("lazada.co.id/", "lazada.com/")),
    ("blibli", ("blibli.com/",)),
    ("zalora", ("zalora.co.id/", "zalora.com/")),
)

# ============================================================
# Tech / tooling detection (substring -> label)
# ============================================================
_TECH_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("calendly", ("calendly.com",)),
    ("acuity", ("acuityscheduling.com", "squarespace-scheduling")),
    ("setmore", ("setmore.com",)),
    ("zocdoc", ("zocdoc.com",)),
    (
        "booking_widget",
        (
            "book now",
            "book an appointment",
            "request appointment",
            "schedule a consultation",
            "book online",
        ),
    ),
    ("intercom", ("intercom.io", "widget.intercom")),
    ("drift", ("drift.com", "js.driftt.com")),
    ("tawk", ("tawk.to",)),
    ("zendesk", ("zendesk.com", "zdassets.com")),
    ("livechat", ("livechatinc.com", "livechat.com")),
    ("hubspot_chat", ("js.hs-scripts.com", "js.usemessages.com")),
    (
        "fb_messenger_chat",
        (
            "connect.facebook.net/en_us/sdk/xfbml.customerchat",
            "fb-customerchat",
        ),
    ),
    ("stripe", ("js.stripe.com", "stripe.com/v3")),
    ("paypal", ("paypal.com/sdk", "paypalobjects.com")),
    ("square", ("squareup.com", "square.site")),
    ("mailchimp", ("mailchimp.com", "list-manage.com", "chimpstatic.com")),
    ("klaviyo", ("klaviyo.com", "static.klaviyo.com")),
    ("activecampaign", ("activehosted.com", "activecampaign.com")),
    ("convertkit", ("convertkit.com", "ck.page")),
    ("hubspot", ("js.hsforms.net", "hs-analytics.net")),
    ("trustpilot", ("trustpilot.com",)),
    ("google_reviews", ("google.com/maps", "g.page/")),
    ("midtrans", ("midtrans.com", "snap.midtrans.com")),
    ("xendit", ("xendit.co", "checkout.xendit.co")),
    ("doku", ("doku.com",)),
    ("whatsapp_button", ("api.whatsapp.com/send", "wa.me/")),
)

_EMPLOYEE_COUNT_RE = re.compile(
    r"(?:team of|staff of|over|more than|tim kami|jumlah karyawan|memiliki)\s*(\d{1,4})\s*"
    r"(?:employees|staff|team members|professionals|experts|specialists|"
    r"doctors|dentists|providers|people|karyawan|orang|tim)",
    re.IGNORECASE,
)
_EMPLOYEE_PLUS_RE = re.compile(
    r"(\d{1,4})\+?\s*"
    r"(?:employees|staff|team members|professionals|experts|specialists|"
    r"doctors|dentists|providers|karyawan|orang|tim)",
    re.IGNORECASE,
)
_FOUNDED_RE = re.compile(
    r"(?:since|est\.?|established(?:\s+in)?|founded(?:\s+in)?|serving[^.]{0,30}?since|"
    r"didirikan(?:\s+pada)?|berdiri\s+(?:sejak|tahun)|sejak\s+tahun)\s*"
    r"((?:19|20)\d{2})",
    re.IGNORECASE,
)

_MULTILOC_KEYWORDS = (
    "our locations",
    "all locations",
    "find a location",
    "store locator",
    "stockist",
    "stockists",
    "store locations",
    "our offices",
    "branches",
    "multiple locations",
    "view all locations",
    "lokasi kami",
    "cari toko",
    "toko kami",
    "cabang",
    "outlet kami",
    "daftar toko",
)

_FASHION_KEYWORDS = (
    "fashion",
    "apparel",
    "footwear",
    "streetwear",
    "batik",
    "hijab",
    "activewear",
    "retail",
    "store",
    "shopping",
    "catalog",
    "collection",
    "pakaian",
    "baju",
    "sepatu",
    "tas",
)

_SKINCARE_KEYWORDS = (
    "skincare",
    "skin care",
    "beauty",
    "kosmetik",
    "cosmetic",
    "serum",
    "moisturizer",
    "sunscreen",
    "facial",
    "kecantikan",
    "perawatan kulit",
    "wajah",
)


def _detect_social(html_low: str) -> list[str]:
    found: list[str] = []
    for label, needles in _SOCIAL_PATTERNS:
        for needle in needles:
            idx = html_low.find(needle)
            if idx == -1:
                continue
            window = html_low[max(0, idx - 5): idx + 40]
            if any(noise in window for noise in _SOCIAL_NOISE):
                continue
            found.append(label)
            break
    return list(dict.fromkeys(found))


def _detect_marketplaces(html_low: str) -> list[str]:
    found: list[str] = []
    for label, needles in _MARKETPLACE_PATTERNS:
        if any(needle in html_low for needle in needles):
            found.append(label)
    return list(dict.fromkeys(found))


def _detect_tech(html_low: str) -> list[str]:
    found: list[str] = []
    for label, needles in _TECH_PATTERNS:
        if any(needle in html_low for needle in needles):
            found.append(label)
    return list(dict.fromkeys(found))


def _detect_founded_year(html: str) -> Optional[int]:
    current = datetime.utcnow().year
    best: Optional[int] = None
    for match in _FOUNDED_RE.finditer(html):
        try:
            year = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if 1850 <= year <= current:
            if best is None or year < best:
                best = year
    return best


def _bucket_employees(n: int) -> str:
    if n <= 10:
        return "1-10"
    if n <= 50:
        return "11-50"
    if n <= 200:
        return "51-200"
    if n <= 500:
        return "201-500"
    return "500+"


def _detect_location_count(html: str, html_low: str) -> int:
    phones = re.findall(r"\+?\d[\d\-\s\(\)]{8,}\d", html)
    normalized = {
        re.sub(r"\D", "", p)[-10:]
        for p in phones
        if len(re.sub(r"\D", "", p)) >= 7
    }
    phone_locations = len(normalized)

    multiloc = any(keyword in html_low for keyword in _MULTILOC_KEYWORDS)

    if multiloc and phone_locations >= 3:
        return max(phone_locations, 3)
    if multiloc:
        return max(phone_locations, 2)
    if phone_locations >= 1:
        return 1
    return 1


def _detect_employee_range(
    html: str,
    html_low: str,
    location_count: int,
) -> tuple[str, str]:
    num: Optional[int] = None
    match = _EMPLOYEE_COUNT_RE.search(html) or _EMPLOYEE_PLUS_RE.search(html)
    if match:
        try:
            num = int(match.group(1))
        except (TypeError, ValueError):
            num = None
    if num is not None:
        return _bucket_employees(num), "explicit"

    has_careers = any(
        keyword in html_low
        for keyword in (
            "careers",
            "join our team",
            "we're hiring",
            "we are hiring",
            "open positions",
            "job openings",
            "karir",
            "lowongan",
            "bergabung",
        )
    )

    if location_count >= 5:
        return "201-500", "heuristic_multi_location"
    if location_count >= 2:
        return "51-200", "heuristic_multi_location"
    if has_careers:
        return "11-50", "heuristic_careers_page"
    return "1-10", "heuristic_default"


def _apply_tier_override(
    *,
    employee_range: str,
    employee_source: str,
    tier: Optional[int],
    brand: Optional[str],
    marketplaces: list[str],
) -> tuple[str, str, list[str]]:
    """Tier-aware override: kalau YAML kasih tier=1, asumsikan brand established.

    Logic:
    - Tier 1: brand market leader -> minimal 201-500 staff, source = tier_metadata_override
    - Tier 2: brand scaling -> minimal 51-200 staff
    - Tier 3: emerging -> minimal 11-50 staff
    - Tetap honor explicit detection kalau lebih besar
    """
    notes: list[str] = []
    if employee_source == "explicit":
        return employee_range, employee_source, notes

    if not tier:
        # Marketplace presence boost tanpa tier
        if len(marketplaces) >= 2 and employee_range == "1-10":
            notes.append("marketplace_presence_size_boost")
            return "11-50", "heuristic_marketplace_presence", notes
        return employee_range, employee_source, notes

    # Mapping size order
    size_order = {"1-10": 0, "11-50": 1, "51-200": 2, "201-500": 3, "500+": 4, "unknown": -1}
    current_idx = size_order.get(employee_range, 0)

    if tier == 1:
        target = "201-500"
        target_idx = size_order[target]
        if current_idx < target_idx:
            notes.append("tier1_size_override_applied")
            return target, "tier_metadata_override", notes
    elif tier == 2:
        target = "51-200"
        target_idx = size_order[target]
        if current_idx < target_idx:
            notes.append("tier2_size_override_applied")
            return target, "tier_metadata_override", notes
    elif tier == 3:
        target = "11-50"
        target_idx = size_order[target]
        if current_idx < target_idx:
            notes.append("tier3_size_override_applied")
            return target, "tier_metadata_override", notes

    # Marketplace presence boost (kalau brand jualan di Shopee/TikTok Shop, biasanya >10 staff)
    if len(marketplaces) >= 2 and employee_range == "1-10":
        notes.append("marketplace_presence_size_boost")
        return "11-50", "heuristic_marketplace_presence", notes

    return employee_range, employee_source, notes


def _compute_bi_score(
    *,
    social_profiles: list[str],
    tech_signals: list[str],
    founded_year: Optional[int],
    employee_range: str,
    location_count: int,
    marketplaces: list[str],
) -> int:
    """Indeks sophistication 0-100 (makin tinggi = bisnis makin mapan)."""
    score = 0.0
    score += min(len(social_profiles), 4) * 6.0
    score += min(len(tech_signals), 6) * 6.0
    if founded_year is not None:
        score += 12.0
    headcount_points = {
        "1-10": 4.0,
        "11-50": 8.0,
        "51-200": 12.0,
        "201-500": 14.0,
        "500+": 16.0,
    }
    score += headcount_points.get(employee_range, 0.0)
    score += min(location_count, 6) * 2.0
    score += min(len(marketplaces), 4) * 4.0
    return max(0, min(100, int(round(score))))


def _is_fashion_like_from_text(text: str) -> bool:
    low = text.lower()
    return any(keyword in low for keyword in _FASHION_KEYWORDS)


def _is_skincare_like_from_text(text: str) -> bool:
    low = text.lower()
    return any(keyword in low for keyword in _SKINCARE_KEYWORDS)


def _infer_firmographics_confidence(
    *,
    employee_source: str,
    social_profiles: list[str],
    tech_signals: list[str],
    founded_year: Optional[int],
    location_count: int,
    html_low: str,
    tier: Optional[int],
    brand: Optional[str],
    marketplaces: list[str],
) -> tuple[str, list[str]]:
    """Infer firmographics confidence dengan multi-signal evidence."""
    flags: list[str] = []

    if employee_source == "explicit":
        flags.append("firmographics_explicit_detection")
    elif employee_source == "tier_metadata_override":
        flags.append("firmographics_tier_assisted")
    else:
        flags.append("firmographics_estimated")

    if founded_year is None:
        flags.append("founded_year_missing")

    if not social_profiles:
        flags.append("social_signals_sparse")

    if not tech_signals:
        flags.append("tech_signals_sparse")

    if marketplaces:
        flags.append(f"marketplace_presence_{len(marketplaces)}")

    if brand:
        flags.append("brand_name_verified")

    if _is_fashion_like_from_text(html_low) or _is_skincare_like_from_text(html_low):
        if employee_source == "heuristic_default" and not tier:
            flags.append("retail_brand_headcount_may_be_underestimated")

    # Confidence inference
    if employee_source == "explicit":
        if founded_year is not None or location_count >= 2 or len(social_profiles) >= 2:
            return "high", flags
        return "medium", flags

    if employee_source == "tier_metadata_override":
        # Tier dari YAML adalah ground truth dari researcher, confidence naik
        if tier == 1 and (len(social_profiles) >= 3 or len(marketplaces) >= 2 or brand):
            return "high", flags
        return "medium", flags

    evidence = 0
    if founded_year is not None:
        evidence += 1
    if len(social_profiles) >= 2:
        evidence += 1
    if len(tech_signals) >= 2:
        evidence += 1
    if location_count >= 2:
        evidence += 1
    if len(marketplaces) >= 2:
        evidence += 1
    if brand:
        evidence += 1

    if evidence >= 4:
        return "medium", flags
    return "low", flags


def _build_detection_notes(
    *,
    firmographics_confidence: str,
    employee_source: str,
    tier: Optional[int],
    marketplaces: list[str],
) -> str:
    """Build detection notes dalam Bahasa Indonesia."""
    notes = []

    if employee_source == "explicit":
        notes.append("Ukuran perusahaan terdeteksi eksplisit dari konten HTML.")
    elif employee_source == "tier_metadata_override":
        notes.append(
            f"Ukuran perusahaan diestimasi berdasarkan tier {tier} dari metadata target (researcher-verified)."
        )
    elif employee_source == "heuristic_marketplace_presence":
        notes.append(
            "Ukuran perusahaan dinaikkan karena terdeteksi presence di multiple marketplace."
        )
    else:
        notes.append("Firmografi diestimasi dari HTML publik dengan heuristik zero-budget.")
        notes.append("Estimasi karyawan & revenue bisa understated untuk brand besar.")

    if marketplaces:
        notes.append(
            f"Brand teridentifikasi punya presence di marketplace: {', '.join(marketplaces)}."
        )

    if firmographics_confidence == "low":
        notes.append("Gunakan dengan hati-hati sebelum klaim audit ke brand.")
    elif firmographics_confidence == "medium":
        notes.append("Data partial — sebagian sinyal terverifikasi, sebagian estimasi.")
    else:
        notes.append("Data relatif terverifikasi dari multiple sinyal publik.")

    return " ".join(notes)


def enrich_business_intelligence(
    html: str,
    domain: str = "",
    *,
    tier: Optional[int] = None,
    brand: Optional[str] = None,
) -> dict[str, Any]:
    """Extract profil BI dari HTML. Selalu return dict lengkap (fail-safe).

    Args:
        html: HTML mentah dari website target.
        domain: domain untuk logging.
        tier: tier dari targets.yaml metadata (1=top, 2=mid, 3=emerging).
        brand: brand name dari targets.yaml metadata.
    """
    default: dict[str, Any] = {
        "employee_range": "unknown",
        "location_count": 0,
        "founded_year": None,
        "years_in_business": None,
        "social_profiles": [],
        "tech_signals": [],
        "marketplaces": [],
        "bi_score": 0,
        "firmographics_confidence": "low",
        "firmographics_source": "free_enrichment",
        "detection_notes": (
            "Firmografi tidak tersedia. Sinyal HTML publik tidak ditemukan atau tidak mencukupi."
        ),
        "data_quality_flags": ["firmographics_unavailable"],
    }
    if not html:
        return default

    try:
        html_low = html.lower()
        social = _detect_social(html_low)
        tech = _detect_tech(html_low)
        marketplaces = _detect_marketplaces(html_low)
        founded = _detect_founded_year(html)
        location_count = _detect_location_count(html, html_low)
        employee_range_raw, employee_source_raw = _detect_employee_range(
            html,
            html_low,
            location_count,
        )

        employee_range, employee_source, override_notes = _apply_tier_override(
            employee_range=employee_range_raw,
            employee_source=employee_source_raw,
            tier=tier,
            brand=brand,
            marketplaces=marketplaces,
        )

        years = None
        if founded is not None:
            years = max(0, datetime.utcnow().year - founded)

        bi_score = _compute_bi_score(
            social_profiles=social,
            tech_signals=tech,
            founded_year=founded,
            employee_range=employee_range,
            location_count=location_count,
            marketplaces=marketplaces,
        )
        firmographics_confidence, flags = _infer_firmographics_confidence(
            employee_source=employee_source,
            social_profiles=social,
            tech_signals=tech,
            founded_year=founded,
            location_count=location_count,
            html_low=html_low,
            tier=tier,
            brand=brand,
            marketplaces=marketplaces,
        )
        flags.extend(override_notes)

        detection_notes = _build_detection_notes(
            firmographics_confidence=firmographics_confidence,
            employee_source=employee_source,
            tier=tier,
            marketplaces=marketplaces,
        )

        return {
            "employee_range": employee_range,
            "location_count": location_count,
            "founded_year": founded,
            "years_in_business": years,
            "social_profiles": social,
            "tech_signals": tech,
            "marketplaces": marketplaces,
            "bi_score": bi_score,
            "firmographics_confidence": firmographics_confidence,
            "firmographics_source": (
                "tier_metadata_assisted"
                if employee_source == "tier_metadata_override"
                else "free_enrichment"
            ),
            "detection_notes": detection_notes,
            "data_quality_flags": flags,
        }
    except Exception as e:  # noqa: BLE001
        print(f"[bi] {domain} BI enrich fail: {type(e).__name__}: {e}")
        return default


def _is_fashion_like(lead: Any) -> bool:
    niche = (getattr(lead, "niche", None) or "").lower()
    category = (getattr(lead, "category", None) or "").lower()
    text = f"{niche} {category}"
    return any(
        keyword in text
        for keyword in (
            "fashion",
            "apparel",
            "footwear",
            "streetwear",
            "batik",
            "hijab",
            "activewear",
            "marketplace",
            "retail",
        )
    )


def _is_skincare_like(lead: Any) -> bool:
    niche = (getattr(lead, "niche", None) or "").lower()
    category = (getattr(lead, "category", None) or "").lower()
    text = f"{niche} {category}"
    return any(
        keyword in text
        for keyword in (
            "skincare",
            "beauty",
            "kosmetik",
            "cosmetic",
            "sunscreen",
            "kecantikan",
        )
    )


def _tier_label_id(tier: Optional[int]) -> str:
    """Label tier dalam Bahasa Indonesia."""
    if tier == 1:
        return "tier 1 (market leader)"
    if tier == 2:
        return "tier 2 (scaling brand)"
    if tier == 3:
        return "tier 3 (emerging)"
    return ""


def build_bi_summary(lead: Any) -> str:
    """Fallback deterministic BI summary (1-2 kalimat Bahasa Indonesia) dari field lead.

    Dipakai analyst.py kalau AI gak ngasih bi_summary.
    """
    brand = (getattr(lead, "brand", None) or "").strip()
    tier = getattr(lead, "tier", None)
    founded = getattr(lead, "founded_year", None)
    years = getattr(lead, "years_in_business", None)
    emp = getattr(lead, "employee_range", "") or "unknown"
    loc = getattr(lead, "location_count", 0) or 0
    tech = getattr(lead, "tech_signals", []) or []
    social = getattr(lead, "social_profiles", []) or []
    marketplaces = getattr(lead, "marketplaces", []) or []
    revenue_tier = (getattr(lead, "revenue_tier", "") or "").strip()
    platform = (getattr(lead, "platform", "") or "").strip()
    notes = (getattr(lead, "notes", "") or "").strip()
    firmo_conf = (getattr(lead, "firmographics_confidence", "low") or "low").strip().lower()

    confidence_note = ""
    if firmo_conf == "low":
        confidence_note = " Sinyal ukuran perusahaan masih estimasi dari data publik."
    elif firmo_conf == "medium":
        confidence_note = " Sinyal ukuran perusahaan sebagian terverifikasi dari data publik."

    is_fashion = _is_fashion_like(lead)
    is_skincare = _is_skincare_like(lead)
    tier_label = _tier_label_id(tier)

    if is_fashion or is_skincare:
        category_label = "fashion/apparel" if is_fashion else "skincare/beauty"
        parts: list[str] = []

        intro_bits: list[str] = []
        if brand:
            intro_bits.append(f"{brand} adalah brand {category_label} Indonesia")
        else:
            intro_bits.append(f"Brand {category_label} Indonesia")
        if tier_label:
            intro_bits.append(tier_label)
        if revenue_tier and revenue_tier != "unknown":
            intro_bits.append(f"estimasi revenue tier: {revenue_tier}")
        if intro_bits:
            parts.append(", ".join(intro_bits))

        maturity_bits: list[str] = []
        if founded:
            if years:
                maturity_bits.append(f"berdiri {founded} (~{years} tahun)")
            else:
                maturity_bits.append(f"berdiri sejak {founded}")
        if emp and emp != "unknown":
            maturity_bits.append(f"estimasi tim: {emp} orang")
        if loc > 1:
            maturity_bits.append(f"{loc} titik lokasi terdeteksi")
        if maturity_bits:
            parts.append(", ".join(maturity_bits))

        stack_bits: list[str] = []
        if platform:
            stack_bits.append(f"platform website: {platform}")
        if tech:
            stack_bits.append(f"stack teknologi: {', '.join(tech[:4])}")
        if social:
            stack_bits.append(f"social: {', '.join(social[:5])}")
        if marketplaces:
            stack_bits.append(f"marketplace: {', '.join(marketplaces)}")
        if stack_bits:
            parts.append(". ".join(stack_bits))

        if notes:
            parts.append(f"Catatan researcher: {notes}")

        if not parts:
            return (
                f"Brand {category_label} dengan sinyal BI publik terbatas.{confidence_note}"
            ).strip()

        summary = ". ".join(p[0].upper() + p[1:] for p in parts if p) + "."
        return f"{summary}{confidence_note}".strip()

    # Generic fallback (non-fashion, non-skincare)
    parts = []

    if brand:
        if tier_label:
            parts.append(f"{brand} ({tier_label})")
        else:
            parts.append(brand)

    if founded:
        if years:
            parts.append(f"berdiri {founded} (~{years} tahun)")
        else:
            parts.append(f"berdiri sejak {founded}")

    size_bits = []
    if emp and emp != "unknown":
        size_bits.append(f"estimasi tim {emp} orang")
    if loc and loc > 1:
        size_bits.append(f"{loc} lokasi")
    if size_bits:
        parts.append(", ".join(size_bits))

    if tech:
        parts.append(f"stack teknologi: {', '.join(tech[:5])}")

    if social:
        parts.append(f"social: {', '.join(social[:5])}")

    if marketplaces:
        parts.append(f"marketplace: {', '.join(marketplaces)}")

    if revenue_tier and revenue_tier != "unknown":
        parts.append(f"estimasi revenue tier: {revenue_tier}")

    if not parts:
        return f"Sinyal BI publik terbatas.{confidence_note}".strip()

    summary = ". ".join(p[0].upper() + p[1:] for p in parts) + "."
    return f"{summary}{confidence_note}".strip()
