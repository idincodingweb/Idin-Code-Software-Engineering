from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class BusinessIntelTarget:
    domain: str
    brand: str = ""
    tier: int = 3
    location: str = ""
    niche: str = ""
    category: str = ""
    notes: str = ""


@dataclass(slots=True)
class BusinessIntelLead:
    rank: int = 0
    domain: str = ""
    brand: str = ""
    tier: int = 3
    location: str = ""
    niche: str = ""
    category: str = ""
    notes: str = ""
    business_score: int = 0
    business_priority: str = "starter"
    data_confidence: str = "low"
    fetch_status: str = "unknown"
    final_url: str = ""
    website_status_code: int = 0
    marketplace_presence: str = "tidak diketahui"
    marketplace_count: int = 0
    marketplaces: str = ""
    shopee_link_found: str = "tidak"
    tiktok_shop_link_found: str = "tidak"
    tokopedia_link_found: str = "tidak"
    lazada_link_found: str = "tidak"
    blibli_link_found: str = "tidak"
    zalora_link_found: str = "tidak"
    checkout_detected: str = "tidak"
    cart_detected: str = "tidak"
    payment_options_detected: str = "tidak"
    payment_methods: str = ""
    promo_code_box_detected: str = "tidak"
    voucher_signal_detected: str = "tidak"
    whatsapp_checkout_signal: str = "tidak"
    funnel_health_score: int = 0
    funnel_gaps: str = ""
    ad_provider: str = "none"
    meta_ads_count: int = 0
    tiktok_ads_count: int = 0
    ad_dominance_score: int = 0
    ad_intel_confidence: str = "low"
    competitor_1: str = ""
    competitor_2: str = ""
    competitor_3: str = ""
    competitor_set: str = ""
    business_opportunities: str = ""
    outreach_angle: str = ""
    executive_summary: str = ""
    detection_notes: str = ""
    data_quality_flags: str = ""
    raw_signals: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("raw_signals", None)
        return row
