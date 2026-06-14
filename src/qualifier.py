# src/qualifier.py
"""Inverted scoring: makin banyak gap = makin tinggi score = makin gede peluang jual."""
from __future__ import annotations

from typing import Optional

from src.config.niche_loader import load_niche_config
from src.models import EnrichmentResult, QualifiedLead
from src.quality_score import compute_quality_score


def qualify_lead(enrichment: EnrichmentResult) -> QualifiedLead:
    """Konversi EnrichmentResult -> QualifiedLead dengan config-driven score."""
    niche_cfg = load_niche_config(enrichment.niche or "default")
    weights = niche_cfg["qualifier"]["weights"]

    pixel_score = _score_pixels(enrichment)
    pagespeed_score = _score_pagespeed(enrichment.pagespeed_score)
    lcp_score = _score_lcp(enrichment.lcp_ms)
    platform_score = _score_platform(enrichment.platform)

    composite = (
        pixel_score * weights["pixels"]
        + pagespeed_score * weights["pagespeed"]
        + lcp_score * weights["lcp"]
        + platform_score * weights["platform"]
    )

    threshold = niche_cfg["qualifier"]["response_penalty_threshold_ms"]
    factor = niche_cfg["qualifier"]["response_penalty_factor"]

    if enrichment.response_ms is not None and enrichment.response_ms > threshold:
        composite *= 1 - factor

    composite = max(0.0, min(1.0, composite))

    lead = QualifiedLead(
        domain=enrichment.domain,
        location=enrichment.location,
        niche=enrichment.niche,
        category=enrichment.category,
        score=round(composite, 4),
        brand=getattr(enrichment, "brand", None),
        tier=getattr(enrichment, "tier", None),
        notes=getattr(enrichment, "notes", None),
        platform=enrichment.platform,
        meta_pixel_in_html=enrichment.has_meta_pixel,
        tiktok_pixel_in_html=enrichment.has_tiktok_pixel,
        ga4_in_html=enrichment.has_ga4,
        gtm_in_html=enrichment.has_gtm,
        google_ads_in_html=enrichment.has_google_ads,
        pagespeed_score=enrichment.pagespeed_score,
        lcp_ms=enrichment.lcp_ms,
        response_ms=enrichment.response_ms,
        emails_found=list(getattr(enrichment, "emails_found", []) or []),
        mx_valid=getattr(enrichment, "mx_valid", None),
        revenue_tier=getattr(enrichment, "revenue_tier", "unknown"),
        revenue_score=getattr(enrichment, "revenue_score", 0),
        running_meta_ads=getattr(enrichment, "running_meta_ads", None),
        meta_ads_count=getattr(enrichment, "meta_ads_count", None),
        competitors=list(getattr(enrichment, "competitors", []) or []),
        email_statuses=dict(getattr(enrichment, "email_statuses", {}) or {}),
        best_email_status=getattr(enrichment, "best_email_status", "unknown"),
        email_verification_method=getattr(enrichment, "email_verification_method", "none"),
        employee_range=getattr(enrichment, "employee_range", "unknown"),
        location_count=getattr(enrichment, "location_count", 0),
        founded_year=getattr(enrichment, "founded_year", None),
        years_in_business=getattr(enrichment, "years_in_business", None),
        social_profiles=list(getattr(enrichment, "social_profiles", []) or []),
        tech_signals=list(getattr(enrichment, "tech_signals", []) or []),
        bi_score=getattr(enrichment, "bi_score", 0),
    )

    lead.quality_score = compute_quality_score(lead)
    return lead


def _score_pixels(e: EnrichmentResult) -> float:
    """0 pixel = 1.0, fully instrumented = rendah opportunity."""
    core_pixels = [
        e.has_meta_pixel,
        e.has_tiktok_pixel,
        e.has_ga4,
        e.has_gtm,
        e.has_google_ads,
    ]
    present = sum(core_pixels)

    if present == 0:
        return 1.00
    if present == 1:
        return 0.88
    if present == 2:
        return 0.70
    if present == 3:
        return 0.48
    if present == 4:
        return 0.24
    return 0.10


def _score_pagespeed(score: Optional[int]) -> float:
    if score is None:
        return 0.50
    if score < 30:
        return 1.00
    if score < 50:
        return 0.85
    if score < 70:
        return 0.60
    if score < 85:
        return 0.35
    return 0.10


def _score_lcp(lcp_ms: Optional[int]) -> float:
    if lcp_ms is None:
        return 0.50
    if lcp_ms > 6000:
        return 1.00
    if lcp_ms > 4000:
        return 0.80
    if lcp_ms > 2500:
        return 0.50
    return 0.10


def _score_platform(platform: Optional[str]) -> float:
    if not platform:
        return 0.50
    p = platform.lower()
    if p in ("wordpress", "woocommerce"):
        return 1.00
    if p in ("shopify", "bigcommerce"):
        return 0.80
    if p in ("wix", "squarespace", "webflow", "duda"):
        return 0.60
    return 0.40
