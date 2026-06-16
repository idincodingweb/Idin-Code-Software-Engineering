from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Any

import httpx

from src.business_models import BusinessIntelLead, BusinessIntelTarget

MARKETPLACE_PATTERNS = {
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


@dataclass
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
        }
        self.client = httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=headers)

    async def close(self):
        await self.client.aclose()

    async def fetch(self, domain: str) -> FetchResult:
        candidates = ["https://" + domain, "http://" + domain]
        last_error = "unreachable"
        for url in candidates:
            try:
                response = await self.client.get(url)
                html = response.text
                status = "ok" if response.is_success else "http_" + str(response.status_code)
                return FetchResult(
                    final_url=str(response.url),
                    status_code=response.status_code,
                    html=html,
                    fetch_status=status,
                )
            except httpx.TimeoutException:
                last_error = "timeout"
            except httpx.HTTPError:
                last_error = "http_error"
        return FetchResult(final_url="", status_code=0, html="", fetch_status=last_error)


class BusinessIntelResearcher:
    def __init__(self, timeout_seconds: float, user_agent: str):
        self.fetcher = WebsiteFetcher(timeout_seconds=timeout_seconds, user_agent=user_agent)

    async def close(self):
        await self.fetcher.close()

    async def research(self, target: BusinessIntelTarget, competitors):
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

        funnel_health_score, funnel_gaps = compute_funnel_health(
            checkout_detected=checkout_detected,
            cart_detected=cart_detected,
            payment_methods=payment_methods,
            promo_detected=promo_detected,
            whatsapp_detected=whatsapp_detected,
            marketplaces=marketplace_matches,
        )
        business_score = compute_business_score(
            tier=target.tier,
            funnel_health_score=funnel_health_score,
            marketplace_count=len(marketplace_matches),
            promo_detected=promo_detected,
        )
        priority = classify_priority(business_score)
        opportunities = build_business_opportunities(
            target=target,
            funnel_health_score=funnel_health_score,
            funnel_gaps=funnel_gaps,
            marketplaces=marketplace_matches,
            promo_detected=promo_detected,
        )
        outreach_angle = build_outreach_angle(target, funnel_health_score, marketplace_matches)
        summary = build_executive_summary(
            target=target,
            funnel_health_score=funnel_health_score,
            marketplaces=marketplace_matches,
            fetch_status=fetch_result.fetch_status,
        )
        flags = build_quality_flags(fetch_result.fetch_status, marketplace_matches, payment_methods)
        notes = build_detection_notes(fetch_result.fetch_status)
        confidence = derive_data_confidence(fetch_result.fetch_status, payment_methods, marketplace_matches)

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
            competitor_1=competitors[0] if len(competitors) > 0 else "",
            competitor_2=competitors[1] if len(competitors) > 1 else "",
            competitor_3=competitors[2] if len(competitors) > 2 else "",
            competitor_set=", ".join(competitors),
            business_opportunities=opportunities,
            outreach_angle=outreach_angle,
            executive_summary=summary,
            detection_notes=notes,
            data_quality_flags=", ".join(flags),
        )


def detect_marketplaces(html: str):
    matches = []
    decoded = unescape(html)
    for name, pattern in MARKETPLACE_PATTERNS.items():
        if pattern.search(decoded):
            matches.append(name)
    return matches


def detect_payment_methods(lower_html: str):
    methods = []
    for keyword, label in PAYMENT_KEYWORDS.items():
        if keyword in lower_html and label not in methods:
            methods.append(label)
    return methods


def detect_any(lower_html: str, patterns):
    for pattern in patterns:
        if re.search(pattern, lower_html, re.IGNORECASE):
            return True
    return False


def compute_funnel_health(checkout_detected, cart_detected, payment_methods, promo_detected, whatsapp_detected, marketplaces):
    score = 35
    gaps = []

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


def compute_business_score(tier, funnel_health_score, marketplace_count, promo_detected):
    score = 50
    score += max(0, 70 - funnel_health_score) // 2
    score += min(10, marketplace_count * 3)
    if not promo_detected:
        score += 4
    if tier == 2:
        score += 6
    elif tier == 3:
        score += 10
    return max(0, min(score, 100))


def classify_priority(score):
    if score >= 85:
        return "premium_gold"
    if score >= 70:
        return "pro"
    if score >= 55:
        return "starter"
    return "all"


def build_business_opportunities(target, funnel_health_score, funnel_gaps, marketplaces, promo_detected):
    parts = []
    if marketplaces:
        parts.append(
            "Brand masih menunjukkan ketergantungan ke marketplace ("
            + ", ".join(marketplaces)
            + "), jadi ada peluang mendorong penjualan direct ke website sendiri untuk jaga margin."
        )
    if funnel_health_score < 60:
        parts.append(
            "Funnel health baru " + str(funnel_health_score) + "/100; gap utama: "
            + "; ".join(funnel_gaps[:3]) + "."
        )
    if not promo_detected:
        parts.append("Signal promo/voucher tidak terlihat, padahal mekanisme ini sering dipakai untuk menutup conversion gap pada traffic berbayar.")
    if target.tier >= 2:
        parts.append("Brand tier scaling seperti ini biasanya responsif terhadap insight yang langsung mengaitkan margin, conversion rate, dan ketergantungan marketplace.")
    return " ".join(parts)


def build_outreach_angle(target, funnel_health_score, marketplaces):
    brand_name = target.brand or target.domain
    if funnel_health_score < 60:
        return "Subject: Ada beberapa friction di funnel " + brand_name + " yang berpotensi menahan konversi direct checkout"
    if marketplaces:
        return "Subject: Observasi " + brand_name + " - peluang memperkuat penjualan direct tanpa terlalu bergantung marketplace"
    return "Subject: Riset singkat bisnis " + brand_name + " - opportunity assessment untuk pertumbuhan direct sales"


def build_executive_summary(target, funnel_health_score, marketplaces, fetch_status):
    brand_name = target.brand or target.domain
    marketplace_text = ", ".join(marketplaces) if marketplaces else "tidak terdeteksi"
    return (
        brand_name + " dianalisis untuk business-intelligence ringan dengan fokus funnel health dan ketergantungan marketplace. "
        + "Fetch status: " + fetch_status + ". "
        + "Funnel health: " + str(funnel_health_score) + "/100. "
        + "Marketplace presence: " + marketplace_text + "."
    )


def build_quality_flags(fetch_status, marketplaces, payment_methods):
    flags = []
    if fetch_status != "ok":
        flags.append("fetch_" + fetch_status)
    if marketplaces:
        flags.append("marketplace_presence_detected")
    else:
        flags.append("marketplace_presence_not_detected")
    if not payment_methods:
        flags.append("payment_methods_not_visible_in_static_html")
    return flags


def build_detection_notes(fetch_status):
    parts = [
        "Website dianalisis via HTML publik tanpa eksekusi JavaScript penuh.",
        "Fetch status: " + fetch_status + ".",
        "Deteksi funnel dan marketplace bersifat research-grade; validasi manual tetap disarankan untuk lead prioritas tinggi.",
    ]
    return " ".join(parts)


def derive_data_confidence(fetch_status, payment_methods, marketplaces):
    if fetch_status != "ok":
        return "low"
    score = 0
    if payment_methods:
        score += 1
    if marketplaces:
        score += 1
    if score >= 2:
        return "medium"
    if score >= 1:
        return "medium"
    return "low"


def yes_no(value):
    return "ya" if value else "tidak"
