from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.business_models import BusinessIntelLead, BusinessIntelTarget


# =========================================================================
# MARKETPLACE PATTERNS
# =========================================================================
MARKETPLACE_PATTERNS = {
    "Shopee": re.compile(r"shopee\.(co\.id|com|sg|my|ph|th|vn|tw)", re.IGNORECASE),
    "TikTok Shop": re.compile(r"tiktok\.com/(?:@|shop|view)|shop\.tiktok\.com|vt\.tiktok\.com", re.IGNORECASE),
    "Tokopedia": re.compile(r"tokopedia\.com", re.IGNORECASE),
    "Lazada": re.compile(r"lazada\.(co\.id|com|sg|my|ph|th|vn)", re.IGNORECASE),
    "Blibli": re.compile(r"blibli\.com", re.IGNORECASE),
    "Zalora": re.compile(r"zalora\.(co\.id|com|sg|my|ph|th|vn)", re.IGNORECASE),
}


# =========================================================================
# PAYMENT GATEWAY / METHOD KEYWORDS
# =========================================================================
PAYMENT_KEYWORDS = {
    "midtrans": "Midtrans",
    "xendit": "Xendit",
    "duitku": "Duitku",
    "ipaymu": "iPaymu",
    "doku": "DOKU",
    "faspay": "Faspay",
    "gopay": "GoPay",
    "ovo": "OVO",
    "dana": "DANA",
    "shopeepay": "ShopeePay",
    "linkaja": "LinkAja",
    "bca virtual account": "BCA Virtual Account",
    "virtual account": "Virtual Account",
    "credit card": "Credit Card",
    "kartu kredit": "Kartu Kredit",
    "bank transfer": "Bank Transfer",
    "transfer bank": "Transfer Bank",
    "cod": "COD",
    "qris": "QRIS",
    "kredivo": "Kredivo",
    "akulaku": "Akulaku",
}


# =========================================================================
# CART BUTTON KEYWORDS (Layer 1: Add-to-Cart / Add-to-Bag / Add-to-Basket)
# =========================================================================
# Format: (regex pattern, label, weight)
# Weight: 3=strong signal, 2=medium, 1=weak
CART_TEXT_PATTERNS = [
    (r"\badd\s+to\s+cart\b", "Add to Cart", 3),
    (r"\badd\s+to\s+bag\b", "Add to Bag", 3),
    (r"\badd\s+to\s+basket\b", "Add to Basket", 3),
    (r"\btambah\s+ke\s+keranjang\b", "Tambah ke Keranjang", 3),
    (r"\bmasukkan\s+(?:ke\s+)?keranjang\b", "Masukkan Keranjang", 3),
    (r"\bmasukkan\s+ke\s+bag\b", "Masukkan ke Bag", 3),
]

# Strong HTML attribute signals (very low false positive)
CART_ATTR_PATTERNS = [
    r'class=["\'][^"\']*\badd[-_]to[-_](?:cart|bag|basket)\b[^"\']*["\']',
    r'id=["\'][^"\']*\badd[-_]?to[-_]?(?:cart|bag|basket)\b[^"\']*["\']',
    r'data-action=["\'][^"\']*\badd[-_]to[-_](?:cart|bag|basket)\b[^"\']*["\']',
    r'aria-label=["\'][^"\']*\badd\s+to\s+(?:cart|bag|basket)\b[^"\']*["\']',
    r'name=["\']add-to-cart["\']',
]


# =========================================================================
# CHECKOUT KEYWORDS (Layer 2: REAL checkout funnel di domain sendiri)
# =========================================================================
# Strong signals — high confidence
CHECKOUT_STRONG_TEXT = [
    (r"\bproceed\s+to\s+checkout\b", "Proceed to Checkout"),
    (r"\bgo\s+to\s+checkout\b", "Go to Checkout"),
    (r"\blanjut(?:kan)?\s+(?:ke\s+)?(?:pembayaran|checkout)\b", "Lanjut ke Pembayaran"),
    (r"\bplace\s+order\b", "Place Order"),
    (r"\bcomplete\s+(?:your\s+)?order\b", "Complete Order"),
    (r"\bbuat\s+pesanan\b", "Buat Pesanan"),
    (r"\bkonfirmasi\s+pesanan\b", "Konfirmasi Pesanan"),
]

CHECKOUT_URL_PATTERNS = [
    r'href=["\'][^"\']*/checkout[/"\'?]',
    r'href=["\'][^"\']*/cart[/"\'?]',
    r'href=["\'][^"\']*/payment[/"\'?]',
    r'action=["\'][^"\']*/checkout[/"\'?]',
]

# "Buy Now" / "Beli Sekarang" — bypass cart langsung ke payment
BUY_NOW_PATTERNS = [
    (r"\bbuy\s+now\b", "Buy Now"),
    (r"\bbeli\s+(?:sekarang|langsung)\b", "Beli Sekarang/Langsung"),
    (r"\border\s+now\b", "Order Now"),
    (r"\bpesan\s+sekarang\b", "Pesan Sekarang"),
]


# =========================================================================
# WHATSAPP CHECKOUT KEYWORDS (Layer 3: CS-based funnel)
# =========================================================================
WHATSAPP_CHECKOUT_STRONG = [
    r"\bpesan\s+(?:via|lewat|melalui)\s+(?:wa|whatsapp)\b",
    r"\border\s+(?:via|through)\s+whatsapp\b",
    r"\bcheckout\s+(?:via|lewat)\s+(?:wa|whatsapp)\b",
    r"\bkonsultasi\s+(?:via|lewat)\s+whatsapp\b",
    r"\bchat\s+(?:admin|cs|customer\s+service)\b",
    r"\bhubungi\s+(?:admin|cs|customer\s+service)\b",
]

WHATSAPP_LINK_PATTERNS = [
    r"wa\.me/\d+",
    r"api\.whatsapp\.com/send",
    r"whatsapp://send",
]


# =========================================================================
# PROMO PATTERNS
# =========================================================================
PROMO_PATTERNS = [
    r"\bpromo\s+code\b",
    r"\bkode\s+promo\b",
    r"\bvoucher\s+code\b",
    r"\bkode\s+voucher\b",
    r"\bcoupon\s+code\b",
    r"\bkode\s+kupon\b",
    r"\bdiskon\s+tambahan\b",
    r"\bapply\s+(?:promo|voucher|coupon)\b",
]

VOUCHER_PATTERNS = [
    r"\bvoucher\b",
    r"\bkupon\b",
    r"\bcashback\b",
]


@dataclass
class FetchResult:
    final_url: str
    status_code: int
    html: str
    fetch_status: str


@dataclass
class DetectionResult:
    detected: bool
    confidence: str
    signals: list
    extras: dict


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
        own_domain = _extract_root_domain(fetch_result.final_url) or target.domain

        # Parse DOM proper biar akurat
        soup = None
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")
            except Exception:
                soup = None

        # === DETEKSI BERLAPIS ===
        marketplace_matches, marketplace_link_count = detect_marketplaces(html, soup, own_domain)
        payment_methods = detect_payment_methods(html)
        cart_result = detect_cart(html, soup)
        checkout_result = detect_checkout(html, soup, own_domain)
        whatsapp_result = detect_whatsapp_checkout(html, soup)
        promo_detected = detect_pattern_list(html, PROMO_PATTERNS)
        voucher_detected = detect_pattern_list(html, VOUCHER_PATTERNS)

        # === SCORING ===
        funnel_health_score, funnel_gaps = compute_funnel_health(
            cart_result=cart_result,
            checkout_result=checkout_result,
            payment_methods=payment_methods,
            promo_detected=promo_detected,
            whatsapp_result=whatsapp_result,
            marketplaces=marketplace_matches,
        )

        # DTC Maturity = seberapa matang infrastruktur direct-to-consumer
        dtc_maturity_score, dtc_maturity_level = compute_dtc_maturity(
            cart_result=cart_result,
            checkout_result=checkout_result,
            payment_methods=payment_methods,
            whatsapp_result=whatsapp_result,
            marketplaces=marketplace_matches,
            fetch_status=fetch_result.fetch_status,
        )

        # Marketplace Dependency = seberapa bergantung ke pihak ketiga
        marketplace_dep_score, marketplace_dep_level = compute_marketplace_dependency(
            marketplaces=marketplace_matches,
            marketplace_link_count=marketplace_link_count,
            checkout_result=checkout_result,
            dtc_maturity_score=dtc_maturity_score,
        )

        # Business score (lead value) — kombinasi semua metrik
        business_score = compute_business_score(
            tier=target.tier,
            funnel_health_score=funnel_health_score,
            dtc_maturity_score=dtc_maturity_score,
            marketplace_dep_score=marketplace_dep_score,
            promo_detected=promo_detected,
        )
        priority = classify_priority(business_score)

        checkout_type = determine_checkout_type(
            checkout_result=checkout_result,
            whatsapp_result=whatsapp_result,
            marketplaces=marketplace_matches,
        )

        # === NARASI ===
        opportunities = build_business_opportunities(
            target=target,
            funnel_health_score=funnel_health_score,
            funnel_gaps=funnel_gaps,
            marketplaces=marketplace_matches,
            promo_detected=promo_detected,
            dtc_maturity_level=dtc_maturity_level,
            marketplace_dep_level=marketplace_dep_level,
            checkout_type=checkout_type,
        )
        outreach_angle = build_outreach_angle(
            target=target,
            funnel_health_score=funnel_health_score,
            marketplaces=marketplace_matches,
            checkout_type=checkout_type,
            marketplace_dep_level=marketplace_dep_level,
        )
        summary = build_executive_summary(
            target=target,
            funnel_health_score=funnel_health_score,
            marketplaces=marketplace_matches,
            fetch_status=fetch_result.fetch_status,
            dtc_maturity_score=dtc_maturity_score,
            marketplace_dep_score=marketplace_dep_score,
            checkout_type=checkout_type,
        )
        flags = build_quality_flags(
            fetch_result.fetch_status,
            marketplace_matches,
            payment_methods,
            cart_result,
            checkout_result,
        )
        notes = build_detection_notes(fetch_result.fetch_status, cart_result, checkout_result)
        confidence = derive_data_confidence(
            fetch_status=fetch_result.fetch_status,
            payment_methods=payment_methods,
            marketplaces=marketplace_matches,
            cart_result=cart_result,
            checkout_result=checkout_result,
        )

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
            cart_detected=yes_no(cart_result.detected),
            cart_confidence=cart_result.confidence,
            cart_signals=", ".join(cart_result.signals[:5]),
            cart_button_variant=cart_result.extras.get("variant", ""),
            checkout_detected=yes_no(checkout_result.detected),
            checkout_confidence=checkout_result.confidence,
            checkout_signals=", ".join(checkout_result.signals[:5]),
            checkout_type=checkout_type,
            payment_options_detected=yes_no(bool(payment_methods)),
            payment_methods=", ".join(payment_methods),
            payment_methods_count=len(payment_methods),
            promo_code_box_detected=yes_no(promo_detected),
            voucher_signal_detected=yes_no(voucher_detected),
            whatsapp_checkout_signal=yes_no(whatsapp_result.detected),
            whatsapp_checkout_confidence=whatsapp_result.confidence,
            funnel_health_score=funnel_health_score,
            funnel_gaps="; ".join(funnel_gaps),
            dtc_maturity_score=dtc_maturity_score,
            dtc_maturity_level=dtc_maturity_level,
            marketplace_dependency_score=marketplace_dep_score,
            marketplace_dependency_level=marketplace_dep_level,
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


# =========================================================================
# DETECTION FUNCTIONS — MULTI-SIGNAL, ANTI FALSE-POSITIVE
# =========================================================================

def _extract_root_domain(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = re.sub(r"^www\.", "", host.lower())
        return host.split("/")[0]
    except Exception:
        return ""


def detect_marketplaces(html: str, soup, own_domain: str):
    """Deteksi marketplace presence + hitung jumlah link external ke marketplace."""
    matches = []
    link_count = 0
    if not html:
        return matches, link_count

    decoded = unescape(html)
    for name, pattern in MARKETPLACE_PATTERNS.items():
        if pattern.search(decoded):
            matches.append(name)

    # Hitung jumlah anchor tag yang external ke marketplace
    if soup is not None:
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            for pattern in MARKETPLACE_PATTERNS.values():
                if pattern.search(href):
                    link_count += 1
                    break

    return matches, link_count


def detect_payment_methods(html: str):
    if not html:
        return []
    methods = []
    lower_html = html.lower()
    for keyword, label in PAYMENT_KEYWORDS.items():
        if keyword in lower_html and label not in methods:
            methods.append(label)
    return methods


def detect_cart(html: str, soup) -> DetectionResult:
    """
    Cart detection: deteksi tombol Add-to-Cart / Add-to-Bag / Add-to-Basket.
    Multi-signal: HTML attribute (strong) + button text (medium) + raw text (weak).
    """
    if not html:
        return DetectionResult(False, "low", [], {"variant": ""})

    signals = []
    weight = 0
    variant = ""

    # SIGNAL 1: HTML attribute (paling kuat — gak mungkin false positive)
    for pattern in CART_ATTR_PATTERNS:
        if re.search(pattern, html, re.IGNORECASE):
            signals.append("attribute_match")
            weight += 4
            break  # cukup 1 attribute match

    # SIGNAL 2: Button/anchor text via BeautifulSoup (filter cuma elemen interaktif)
    if soup is not None:
        interactive_texts = []
        for tag in soup.find_all(["button", "a", "input"]):
            text = (tag.get_text(strip=True) or tag.get("value", "") or tag.get("aria-label", "")).lower()
            if text:
                interactive_texts.append(text)

        joined = " | ".join(interactive_texts)
        for pattern, label, w in CART_TEXT_PATTERNS:
            if re.search(pattern, joined, re.IGNORECASE):
                signals.append(label)
                weight += w
                if not variant:
                    variant = label

    # SIGNAL 3: Raw text fallback (weak — kalau soup gagal parse)
    if not signals:
        lower_html = html.lower()
        for pattern, label, w in CART_TEXT_PATTERNS:
            if re.search(pattern, lower_html, re.IGNORECASE):
                signals.append(label + " (raw)")
                weight += max(1, w - 1)  # turunkan weight karena gak terikat ke elemen interaktif
                if not variant:
                    variant = label

    detected = weight >= 2
    if weight >= 5:
        confidence = "high"
    elif weight >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    if not detected:
        confidence = "low"

    return DetectionResult(detected, confidence, signals, {"variant": variant, "weight": weight})


def detect_checkout(html: str, soup, own_domain: str) -> DetectionResult:
    """
    Checkout detection: deteksi REAL checkout funnel di domain sendiri.
    Bukan cuma kata 'checkout' di footer, tapi URL pattern + button text + form action.
    """
    if not html:
        return DetectionResult(False, "low", [], {})

    signals = []
    weight = 0

    # SIGNAL 1: URL pattern /checkout, /cart, /payment di domain sendiri (sangat kuat)
    if soup is not None:
        for anchor in soup.find_all(["a", "form"], href=True) + soup.find_all("form", action=True):
            attr = anchor.get("href") or anchor.get("action") or ""
            if not attr:
                continue
            # Pastikan link ke domain sendiri (atau relative path)
            if attr.startswith("/") or own_domain in attr.lower():
                if re.search(r"/(checkout|payment)(/|$|\?)", attr, re.IGNORECASE):
                    signals.append("checkout_url:" + attr[:60])
                    weight += 5
                    break

    # SIGNAL 2: Strong checkout button text (Proceed to Checkout, Place Order, dll)
    if soup is not None:
        interactive_texts = []
        for tag in soup.find_all(["button", "a", "input"]):
            text = (tag.get_text(strip=True) or tag.get("value", "") or tag.get("aria-label", "")).lower()
            if text:
                interactive_texts.append(text)
        joined = " | ".join(interactive_texts)

        for pattern, label in CHECKOUT_STRONG_TEXT:
            if re.search(pattern, joined, re.IGNORECASE):
                signals.append(label)
                weight += 4
                break

        # SIGNAL 3: Buy Now / Beli Sekarang (bypass cart, tapi tetap funnel)
        for pattern, label in BUY_NOW_PATTERNS:
            if re.search(pattern, joined, re.IGNORECASE):
                signals.append(label)
                weight += 2
                break

    # SIGNAL 4: Form action ke /checkout
    if soup is not None:
        for form in soup.find_all("form", action=True):
            action = form["action"].lower()
            if "/checkout" in action or "/cart" in action or "/payment" in action:
                signals.append("form_action_checkout")
                weight += 3
                break

    # Anti false-positive: kalau cuma weight rendah dari kata di footer, abaikan
    detected = weight >= 4
    if weight >= 7:
        confidence = "high"
    elif weight >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    if not detected:
        confidence = "low"

    return DetectionResult(detected, confidence, signals, {"weight": weight})


def detect_whatsapp_checkout(html: str, soup) -> DetectionResult:
    """Deteksi WhatsApp-based checkout funnel (CS-driven order)."""
    if not html:
        return DetectionResult(False, "low", [], {})

    signals = []
    weight = 0

    # SIGNAL 1: wa.me link (kuat)
    wa_links = re.findall(r"wa\.me/(\d{8,})", html)
    if wa_links:
        signals.append("wa.me_link:" + wa_links[0][:15])
        weight += 3

    if re.search(r"api\.whatsapp\.com/send", html, re.IGNORECASE):
        signals.append("api.whatsapp.com")
        weight += 2

    # SIGNAL 2: Eksplisit "Pesan via WA" / "Order via WhatsApp"
    lower_html = html.lower()
    for pattern in WHATSAPP_CHECKOUT_STRONG:
        if re.search(pattern, lower_html, re.IGNORECASE):
            signals.append("wa_checkout_text")
            weight += 3
            break

    detected = weight >= 3
    if weight >= 5:
        confidence = "high"
    elif weight >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    if not detected:
        confidence = "low"

    return DetectionResult(detected, confidence, signals, {"weight": weight})


def detect_pattern_list(html: str, patterns):
    if not html:
        return False
    lower_html = html.lower()
    for pattern in patterns:
        if re.search(pattern, lower_html, re.IGNORECASE):
            return True
    return False


# =========================================================================
# SCORING FUNCTIONS
# =========================================================================

def compute_funnel_health(cart_result, checkout_result, payment_methods, promo_detected, whatsapp_result, marketplaces):
    """Score 0-100. Tinggi = funnel sehat. Rendah = banyak gap."""
    score = 30
    gaps = []

    # Cart layer
    if cart_result.detected and cart_result.confidence == "high":
        score += 12
    elif cart_result.detected and cart_result.confidence == "medium":
        score += 8
    elif cart_result.detected:
        score += 4
    else:
        gaps.append("Tombol cart/bag/basket tidak terdeteksi di elemen interaktif")

    # Checkout layer
    if checkout_result.detected and checkout_result.confidence == "high":
        score += 22
    elif checkout_result.detected and checkout_result.confidence == "medium":
        score += 14
    elif checkout_result.detected:
        score += 7
    else:
        gaps.append("Checkout funnel di domain sendiri tidak terdeteksi (false hope funnel risk)")

    # Payment methods
    if payment_methods:
        score += min(18, len(payment_methods) * 4)
    else:
        gaps.append("Metode pembayaran tidak terlihat dari HTML publik")

    # Promo
    if promo_detected:
        score += 6
    else:
        gaps.append("Kotak promo/voucher belum terdeteksi")

    # WhatsApp checkout (bonus, bukan substitute)
    if whatsapp_result.detected:
        score += 4

    # Penalty: dependency ke marketplace
    if marketplaces:
        penalty = min(18, len(marketplaces) * 4)
        score -= penalty
        gaps.append("Indikasi funnel diarahkan ke marketplace pihak ketiga (" + ", ".join(marketplaces) + ")")

    return max(0, min(score, 100)), gaps


def compute_dtc_maturity(cart_result, checkout_result, payment_methods, whatsapp_result, marketplaces, fetch_status):
    """
    DTC Maturity Score (0-100):
    Seberapa matang infrastruktur direct-to-consumer brand ini.
    Bobot realistis berdasarkan signal yang paling diagnostik.
    """
    if fetch_status != "ok":
        return 0, "unknown"

    score = 0

    # Native checkout di domain sendiri = signal DTC paling kuat (bobot 40)
    if checkout_result.detected and checkout_result.confidence == "high":
        score += 40
    elif checkout_result.detected and checkout_result.confidence == "medium":
        score += 25
    elif checkout_result.detected:
        score += 12

    # Cart functionality (bobot 20)
    if cart_result.detected and cart_result.confidence == "high":
        score += 20
    elif cart_result.detected and cart_result.confidence == "medium":
        score += 12
    elif cart_result.detected:
        score += 6

    # Payment gateway visibility (bobot 25)
    payment_count = len(payment_methods)
    if payment_count >= 5:
        score += 25
    elif payment_count >= 3:
        score += 18
    elif payment_count >= 1:
        score += 10

    # WhatsApp-only checkout = DTC level rendah (max +5, karena masih semi-direct)
    if whatsapp_result.detected and not checkout_result.detected:
        score += 5
    elif whatsapp_result.detected:
        score += 3

    # Penalty: brand yang banyak marketplace tapi gak punya checkout = anti-DTC
    if marketplaces and not checkout_result.detected:
        score -= min(15, len(marketplaces) * 3)

    score = max(0, min(score, 100))

    if score >= 80:
        level = "mature"
    elif score >= 60:
        level = "developing"
    elif score >= 35:
        level = "emerging"
    elif score >= 15:
        level = "minimal"
    else:
        level = "none"

    return score, level


def compute_marketplace_dependency(marketplaces, marketplace_link_count, checkout_result, dtc_maturity_score):
    """
    Marketplace Dependency Score (0-100):
    Tinggi = brand sangat tergantung marketplace.
    Rendah = brand jalan sendiri di DTC channel.
    """
    if not marketplaces:
        return 5, "none"

    score = 20  # base: ada presence aja

    # Jumlah marketplace
    score += min(30, len(marketplaces) * 8)

    # Jumlah link external ke marketplace (proxy untuk seberapa eksplisit redirect-nya)
    if marketplace_link_count >= 10:
        score += 25
    elif marketplace_link_count >= 5:
        score += 18
    elif marketplace_link_count >= 2:
        score += 10
    elif marketplace_link_count >= 1:
        score += 5

    # Kalau checkout sendiri gak ada = dependency makin tinggi
    if not checkout_result.detected:
        score += 20

    # Kalau DTC maturity rendah = dependency tinggi
    if dtc_maturity_score < 30:
        score += 10

    score = max(0, min(score, 100))

    if score >= 75:
        level = "critical"
    elif score >= 55:
        level = "high"
    elif score >= 35:
        level = "medium"
    elif score >= 15:
        level = "low"
    else:
        level = "none"

    return score, level


def compute_business_score(tier, funnel_health_score, dtc_maturity_score, marketplace_dep_score, promo_detected):
    """
    Business Score (0-100) = nilai lead untuk outreach.
    Tinggi = lead bagus. Logic: brand yang gap-nya jelas + tier scaling = peluang tertinggi.
    """
    score = 40

    # Funnel gap = opportunity untuk pitching (max +25)
    score += max(0, 70 - funnel_health_score) // 3

    # Marketplace dependency tinggi = pain point jelas (max +20)
    score += marketplace_dep_score // 5

    # DTC maturity rendah (tapi ada brand awareness) = high-fit pitch (max +15)
    if dtc_maturity_score < 50:
        score += (50 - dtc_maturity_score) // 4

    if not promo_detected:
        score += 3

    # Tier bobot
    if tier == 1:
        score += 2
    elif tier == 2:
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


def determine_checkout_type(checkout_result, whatsapp_result, marketplaces):
    """Klasifikasi tipe checkout untuk pitching."""
    if checkout_result.detected and checkout_result.confidence in ("high", "medium"):
        return "native"
    if whatsapp_result.detected and not checkout_result.detected:
        return "whatsapp"
    if marketplaces and not checkout_result.detected and not whatsapp_result.detected:
        return "marketplace_only"
    if checkout_result.detected and marketplaces:
        return "hybrid"
    return "unknown"


# =========================================================================
# NARRATIVE BUILDERS
# =========================================================================

def build_business_opportunities(target, funnel_health_score, funnel_gaps, marketplaces, promo_detected, dtc_maturity_level, marketplace_dep_level, checkout_type):
    parts = []

    if checkout_type == "marketplace_only":
        parts.append(
            "Brand termasuk kategori 'marketplace-only funnel' — semua traffic diarahkan ke pihak ketiga, "
            "yang artinya margin tergerus fee marketplace dan customer data tidak dimiliki brand."
        )
    elif checkout_type == "whatsapp":
        parts.append(
            "Checkout brand bergantung pada WhatsApp/CS manual — skalanya terbatas, tidak ada cart abandonment recovery, "
            "dan tidak ada customer data terstruktur untuk retargeting."
        )
    elif checkout_type == "hybrid":
        parts.append(
            "Brand sudah punya checkout sendiri tapi masih push ke marketplace — 'false hope funnel': customer awareness ada di website, "
            "tapi conversion lari ke pihak ketiga. Opportunity besar untuk optimize on-site conversion."
        )

    if marketplace_dep_level in ("critical", "high"):
        parts.append(
            "Marketplace dependency level: " + marketplace_dep_level + " (" + ", ".join(marketplaces) + "). "
            "Setiap order via marketplace memakan fee 3-8% + commission, plus zero ownership atas customer data."
        )

    if dtc_maturity_level in ("none", "minimal", "emerging"):
        parts.append(
            "DTC maturity level: " + dtc_maturity_level + ". Infrastruktur direct-to-consumer brand ini masih bisa di-level-up "
            "dari sisi cart UX, payment gateway diversification, dan checkout flow."
        )

    if funnel_health_score < 60:
        parts.append(
            "Funnel health: " + str(funnel_health_score) + "/100. Gap utama: " + "; ".join(funnel_gaps[:3]) + "."
        )

    if not promo_detected:
        parts.append(
            "Tidak ada signal promo/voucher di landing page — mekanisme ini biasanya menambah conversion rate 8-15% pada traffic berbayar."
        )

    if target.tier >= 2:
        parts.append(
            "Brand tier scaling responsif terhadap insight yang langsung mengaitkan margin, conversion rate, dan ketergantungan marketplace."
        )

    return " ".join(parts)


def build_outreach_angle(target, funnel_health_score, marketplaces, checkout_type, marketplace_dep_level):
    brand_name = target.brand or target.domain

    if checkout_type == "marketplace_only":
        return (
            "Subject: Observasi " + brand_name + " - semua direct traffic 'kabur' ke marketplace, "
            "ada margin yang bisa diselamatkan"
        )
    if checkout_type == "hybrid":
        return (
            "Subject: Audit funnel " + brand_name + " - traffic landing di website tapi conversion lari ke marketplace, "
            "ini false hope funnel yang bisa dibenerin"
        )
    if checkout_type == "whatsapp":
        return (
            "Subject: " + brand_name + " - checkout via WhatsApp bagus untuk awal, "
            "tapi sudah waktunya scaling ke automated funnel"
        )
    if marketplace_dep_level in ("critical", "high"):
        return (
            "Subject: " + brand_name + " - ketergantungan marketplace " + marketplace_dep_level +
            ", ada peluang reclaim margin"
        )
    if funnel_health_score < 60:
        return (
            "Subject: Beberapa friction di funnel " + brand_name + " yang berpotensi menahan konversi"
        )
    return (
        "Subject: Riset singkat bisnis " + brand_name + " - opportunity assessment untuk pertumbuhan direct sales"
    )


def build_executive_summary(target, funnel_health_score, marketplaces, fetch_status, dtc_maturity_score, marketplace_dep_score, checkout_type):
    brand_name = target.brand or target.domain
    marketplace_text = ", ".join(marketplaces) if marketplaces else "tidak terdeteksi"
    return (
        brand_name + " dianalisis untuk business intelligence. " +
        "Fetch: " + fetch_status + ". " +
        "Funnel health: " + str(funnel_health_score) + "/100. " +
        "DTC maturity: " + str(dtc_maturity_score) + "/100. " +
        "Marketplace dependency: " + str(marketplace_dep_score) + "/100. " +
        "Checkout type: " + checkout_type + ". " +
        "Marketplace presence: " + marketplace_text + "."
    )


def build_quality_flags(fetch_status, marketplaces, payment_methods, cart_result, checkout_result):
    flags = []
    if fetch_status != "ok":
        flags.append("fetch_" + fetch_status)
    if marketplaces:
        flags.append("marketplace_presence_detected")
    else:
        flags.append("marketplace_presence_not_detected")
    if not payment_methods:
        flags.append("payment_methods_not_visible_in_static_html")
    if cart_result.detected and cart_result.confidence == "low":
        flags.append("cart_low_confidence_needs_manual_review")
    if checkout_result.detected and checkout_result.confidence == "low":
        flags.append("checkout_low_confidence_needs_manual_review")
    if not cart_result.detected and not checkout_result.detected and marketplaces:
        flags.append("likely_marketplace_only_funnel")
    return flags


def build_detection_notes(fetch_status, cart_result, checkout_result):
    parts = [
        "Website dianalisis via HTML publik + DOM parsing (BeautifulSoup) tanpa eksekusi JavaScript penuh.",
        "Fetch status: " + fetch_status + ".",
    ]
    if cart_result.detected:
        parts.append("Cart signals: " + ", ".join(cart_result.signals[:3]) + " (confidence: " + cart_result.confidence + ").")
    if checkout_result.detected:
        parts.append("Checkout signals: " + ", ".join(checkout_result.signals[:3]) + " (confidence: " + checkout_result.confidence + ").")
    parts.append("Lead dengan confidence 'medium' disarankan untuk validasi manual cepat sebelum outreach.")
    return " ".join(parts)


def derive_data_confidence(fetch_status, payment_methods, marketplaces, cart_result, checkout_result):
    if fetch_status != "ok":
        return "low"

    score = 0
    if payment_methods:
        score += 1
    if marketplaces:
        score += 1
    if cart_result.detected and cart_result.confidence == "high":
        score += 2
    elif cart_result.detected:
        score += 1
    if checkout_result.detected and checkout_result.confidence == "high":
        score += 2
    elif checkout_result.detected:
        score += 1

    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def yes_no(value):
    return "ya" if value else "tidak"
