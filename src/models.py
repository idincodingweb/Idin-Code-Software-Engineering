# src/models.py
"""Dataclasses untuk pipeline. Type-safe, self-documenting.

ARSITEKTUR:
- Target           -> input mentah dari targets.yaml (dipakai loader.py)
- EnrichmentResult -> hasil enrichment per domain (dipakai enrichers.py)
- QualifiedLead    -> scored lead siap export (dipakai qualifier/analyst/export)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# Input: dari targets.yaml (dipakai loader.py)
# ============================================================
@dataclass
class Target:
    """Single target dari targets.yaml - input mentah sebelum enrichment."""
    domain: str
    location: Optional[str] = None
    niche: str = "default"
    category: Optional[str] = None
    brand: Optional[str] = None
    tier: Optional[int] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert ke dict - kompatibel dengan enrich_domain() yang expect dict."""
        return {
            "domain": self.domain,
            "location": self.location,
            "niche": self.niche,
            "category": self.category,
            "brand": self.brand,
            "tier": self.tier,
            "notes": self.notes,
        }


# ============================================================
# Intermediate: hasil enrichment (dipakai enrichers.py)
# ============================================================
@dataclass
class EnrichmentResult:
    """Raw enrichment data per domain (sebelum scoring)."""
    domain: str
    location: Optional[str]
    niche: str
    category: Optional[str]

    # Source metadata from targets.yaml
    brand: Optional[str] = None
    tier: Optional[int] = None
    notes: Optional[str] = None

    # Reachability
    reachable: bool = False
    fail_reason: Optional[str] = None
    response_ms: Optional[int] = None
    status_code: Optional[int] = None

    # Platform
    platform: Optional[str] = None

    # Pixels (from HTML)
    has_meta_pixel: bool = False
    has_tiktok_pixel: bool = False
    has_ga4: bool = False
    has_gtm: bool = False
    has_google_ads: bool = False

    # Data quality / confidence
    pixel_detection_method: str = "html_regex"
    pixel_confidence: str = "low"
    firmographics_confidence: str = "low"
    data_confidence: str = "low"
    firmographics_source: str = "free_enrichment"
    detection_notes: str = ""
    data_quality_flags: list[str] = field(default_factory=list)

    # Performance (from PageSpeed API)
    pagespeed_score: Optional[int] = None
    lcp_ms: Optional[int] = None

    # Raw HTML (kept for extras layer - NOT exported to CSV)
    raw_html: Optional[str] = field(default=None, repr=False)

    # Extras (filled by src/extras.py - opsional)
    emails_found: list = field(default_factory=list)
    mx_valid: Optional[bool] = None
    revenue_tier: str = "unknown"
    revenue_score: int = 0
    running_meta_ads: Optional[bool] = None
    meta_ads_count: Optional[int] = None
    competitors: list = field(default_factory=list)

    # Email Verification (filled by src/email_verifier.py - opsional)
    email_statuses: dict = field(default_factory=dict)
    best_email_status: str = "unknown"
    email_verification_method: str = "none"

    # Business Intelligence (filled by src/bi_enrich.py - opsional, zero-budget)
    employee_range: str = "unknown"
    location_count: int = 0
    founded_year: Optional[int] = None
    years_in_business: Optional[int] = None
    social_profiles: list = field(default_factory=list)
    tech_signals: list = field(default_factory=list)
    marketplaces: list = field(default_factory=list)
    bi_score: int = 0


# ============================================================
# Final: scored lead siap export
# ============================================================
@dataclass
class QualifiedLead:
    """Scored lead, siap di-enrich AI & export."""
    domain: str
    location: Optional[str]
    niche: str
    category: Optional[str]
    score: float

    # Source metadata from targets.yaml
    brand: Optional[str] = None
    tier: Optional[int] = None
    notes: Optional[str] = None

    platform: Optional[str] = None
    meta_pixel_in_html: bool = False
    tiktok_pixel_in_html: bool = False
    ga4_in_html: bool = False
    gtm_in_html: bool = False
    google_ads_in_html: bool = False

    # Data quality / confidence
    pixel_detection_method: str = "html_regex"
    pixel_confidence: str = "low"
    firmographics_confidence: str = "low"
    data_confidence: str = "low"
    firmographics_source: str = "free_enrichment"
    detection_notes: str = ""
    data_quality_flags: list[str] = field(default_factory=list)

    pagespeed_score: Optional[int] = None
    lcp_ms: Optional[int] = None
    response_ms: Optional[int] = None

    # AI-generated (filled by analyst.py)
    gold_reasons: str = ""
    outreach_angle: str = ""

    # Lead Quality Score 0-100 (deterministic di qualifier, boleh di-override AI)
    quality_score: int = 0
    # Business Intelligence summary (deterministic fallback / AI di analyst.py)
    bi_summary: str = ""

    # Extras (filled by src/extras.py - opsional, all zero-budget)
    emails_found: list = field(default_factory=list)
    mx_valid: Optional[bool] = None
    revenue_tier: str = "unknown"
    revenue_score: int = 0
    running_meta_ads: Optional[bool] = None
    meta_ads_count: Optional[int] = None
    competitors: list = field(default_factory=list)

    # Email Verification (carried from EnrichmentResult)
    email_statuses: dict = field(default_factory=dict)
    best_email_status: str = "unknown"
    email_verification_method: str = "none"

    # Business Intelligence (filled by src/bi_enrich.py - opsional, zero-budget)
    employee_range: str = "unknown"
    location_count: int = 0
    founded_year: Optional[int] = None
    years_in_business: Optional[int] = None
    social_profiles: list = field(default_factory=list)
    tech_signals: list = field(default_factory=list)
    marketplaces: list = field(default_factory=list)
    bi_score: int = 0

    # Rank (assigned by export.py)
    rank: int = 0
