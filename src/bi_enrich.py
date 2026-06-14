# src/bi_enrich.py
"""Business Intelligence Enrichment (zero-budget, HTML-only).

Roadmap v3.4: upgrade dari sekadar revenue tier 1-5 (estimate_revenue_tier di
extras.py — TETEP ADA) ke profil BI yang lebih kaya, semua di-extract dari
HTML publik (gak butuh API berbayar, sejalan dengan prinsip legal software).

Output dict (semua deterministic & fail-safe):
    employee_range   : str   -> "1-10" / "11-50" / "51-200" / "201-500" / "500+" / "unknown"
    location_count   : int   -> estimasi jumlah lokasi/cabang (>=1 kalau reachable)
    founded_year     : int?  -> tahun berdiri kalau ke-detect ("since 2009", dst)
    years_in_business: int?  -> turunan dari founded_year
    social_profiles  : list  -> ["facebook","instagram","linkedin",...]
    tech_signals     : list  -> ["calendly","stripe","intercom","mailchimp",...]
    bi_score         : int   -> 0-100 indeks "kematangan/sophistication" bisnis

Setiap fungsi WAJIB graceful — kalau parsing gagal, return default kosong.
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
# Tech / tooling detection (substring -> label)
# ============================================================
_TECH_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Booking / scheduling
    ("calendly", ("calendly.com",)),
    ("acuity", ("acuityscheduling.com", "squarespace-scheduling")),
    ("setmore", ("setmore.com",)),
    ("zocdoc", ("zocdoc.com",)),
    ("booking_widget", (
        "book now",
        "book an appointment",
        "request appointment",
        "schedule a consultation",
        "book online",
    )),
    # Chat / support
    ("intercom", ("intercom.io", "widget.intercom")),
    ("drift", ("drift.com", "js.driftt.com")),
    ("tawk", ("tawk.to",)),
    ("zendesk", ("zendesk.com", "zdassets.com")),
    ("livechat", ("livechatinc.com", "livechat.com")),
    ("hubspot_chat", ("js.hs-scripts.com", "js.usemessages.com")),
    ("fb_messenger_chat", (
        "connect.facebook.net/en_us/sdk/xfbml.customerchat",
        "fb-customerchat",
    )),
    # Payments
    ("stripe", ("js.stripe.com", "stripe.com/v3")),
    ("paypal", ("paypal.com/sdk", "paypalobjects.com")),
    ("square", ("squareup.com", "square.site")),
    # Email / marketing automation
    ("mailchimp", ("mailchimp.com", "list-manage.com", "chimpstatic.com")),
    ("klaviyo", ("klaviyo.com", "static.klaviyo.com")),
    ("activecampaign", ("activehosted.com", "activecampaign.com")),
    ("convertkit", ("convertkit.com", "ck.page")),
    ("hubspot", ("js.hsforms.net", "hs-analytics.net")),
    # Reviews / trust
    ("trustpilot", ("trustpilot.com",)),
    ("google_reviews", ("google.com/maps", "g.page/")),
)

_EMPLOYEE_COUNT_RE = re.compile(
    r"(?:team of|staff of|over|more than)\s*(\d{1,4})\s*"
    r"(?:employees|staff|team members|professionals|experts|specialists|"
    r"doctors|dentists|providers|people)",
    re.IGNORECASE,
)
_EMPLOYEE_PLUS_RE = re.compile(
    r"(\d{1,4})\+?\s*"
    r"(?:employees|staff|team members|professionals|experts|specialists|"
    r"doctors|dentists|providers)",
    re.IGNORECASE,
)
_FOUNDED_RE = re.compile(
    r"(?:since|est\.?|established(?:\s+in)?|founded(?:\s+in)?|serving[^.]{0,30}?since)\s*"
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


def _detect_employee_range(html: str, html_low: str, location_count: int) -> str:
    num: Optional[int] = None
    match = _EMPLOYEE_COUNT_RE.search(html) or _EMPLOYEE_PLUS_RE.search(html)
    if match:
        try:
            num = int(match.group(1))
        except (TypeError, ValueError):
            num = None
    if num is not None:
        return _bucket_employees(num)

    has_careers = any(
        keyword in html_low
        for keyword in (
            "careers",
            "join our team",
            "we're hiring",
            "we are hiring",
            "open positions",
            "job openings",
        )
    )
    if location_count >= 5:
        return "201-500"
    if location_count >= 2:
        return "51-200"
    if has_careers:
        return "11-50"
    return "1-10"


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


def _compute_bi_score(
    *,
    social_profiles: list[str],
    tech_signals: list[str],
    founded_year: Optional[int],
    employee_range: str,
    location_count: int,
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
    return max(0, min(100, int(round(score))))


def enrich_business_intelligence(html: str, domain: str = "") -> dict[str, Any]:
    """Extract profil BI dari HTML. Selalu return dict lengkap (fail-safe)."""
    default: dict[str, Any] = {
        "employee_range": "unknown",
        "location_count": 0,
        "founded_year": None,
        "years_in_business": None,
        "social_profiles": [],
        "tech_signals": [],
        "bi_score": 0,
    }
    if not html:
        return default

    try:
        html_low = html.lower()
        social = _detect_social(html_low)
        tech = _detect_tech(html_low)
        founded = _detect_founded_year(html)
        location_count = _detect_location_count(html, html_low)
        employee_range = _detect_employee_range(html, html_low, location_count)
        years = None
        if founded is not None:
            years = max(0, datetime.utcnow().year - founded)
        bi_score = _compute_bi_score(
            social_profiles=social,
            tech_signals=tech,
            founded_year=founded,
            employee_range=employee_range,
            location_count=location_count,
        )
        return {
            "employee_range": employee_range,
            "location_count": location_count,
            "founded_year": founded,
            "years_in_business": years,
            "social_profiles": social,
            "tech_signals": tech,
            "bi_score": bi_score,
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


def build_bi_summary(lead: Any) -> str:
    """Fallback deterministic BI summary (1-2 kalimat) dari field lead.

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
    revenue_tier = (getattr(lead, "revenue_tier", "") or "").strip()
    platform = (getattr(lead, "platform", "") or "").strip()
    notes = (getattr(lead, "notes", "") or "").strip()

    if _is_fashion_like(lead):
        parts: list[str] = []

        intro_bits: list[str] = []
        if brand:
            intro_bits.append(brand)
        if tier is not None:
            intro_bits.append(f"tier {tier} target")
        if revenue_tier and revenue_tier != "unknown":
            intro_bits.append(f"revenue tier {revenue_tier}")
        if intro_bits:
            parts.append(", ".join(intro_bits))

        maturity_bits: list[str] = []
        if founded:
            if years:
                maturity_bits.append(f"established {founded} (~{years} yrs)")
            else:
                maturity_bits.append(f"established {founded}")
        if emp and emp != "unknown":
            maturity_bits.append(f"{emp} staff")
        if loc > 1:
            maturity_bits.append(f"{loc} locations")
        if maturity_bits:
            parts.append(", ".join(maturity_bits))

        stack_bits: list[str] = []
        if platform:
            stack_bits.append(f"platform {platform}")
        if tech:
            stack_bits.append(f"tech: {', '.join(tech[:4])}")
        if social:
            stack_bits.append(f"social: {', '.join(social[:5])}")
        if stack_bits:
            parts.append(". ".join(stack_bits))

        if notes:
            parts.append(notes)

        if not parts:
            return "Fashion/e-commerce brand with limited public BI signals detected."

        return ". ".join(p[0].upper() + p[1:] for p in parts if p) + "."

    parts = []

    if founded:
        if years:
            parts.append(f"Established {founded} (~{years} yrs in business)")
        else:
            parts.append(f"Established {founded}")

    size_bits = []
    if emp and emp != "unknown":
        size_bits.append(f"{emp} staff")
    if loc and loc > 1:
        size_bits.append(f"{loc} locations")
    if size_bits:
        parts.append(", ".join(size_bits))

    if tech:
        parts.append(f"tech stack: {', '.join(tech[:5])}")

    if social:
        parts.append(f"social: {', '.join(social[:5])}")

    if revenue_tier and revenue_tier != "unknown":
        parts.append(f"revenue tier: {revenue_tier}")

    if not parts:
        return "Limited public BI signals detected."

    return ". ".join(p[0].upper() + p[1:] for p in parts) + "."
