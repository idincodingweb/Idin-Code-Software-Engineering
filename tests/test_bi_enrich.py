# tests/test_bi_enrich.py
"""Unit tests untuk src/bi_enrich.py — Business Intelligence enrichment."""
from __future__ import annotations

from datetime import datetime

from src.bi_enrich import (
    enrich_business_intelligence,
    build_bi_summary,
)
from src.models import QualifiedLead


def test_empty_html_returns_default():
    out = enrich_business_intelligence("", "x.com")
    assert out["employee_range"] == "unknown"
    assert out["social_profiles"] == []
    assert out["tech_signals"] == []
    assert out["bi_score"] == 0
    assert out["founded_year"] is None


def test_detect_social_profiles():
    html = """
    <a href="https://facebook.com/myclinic">fb</a>
    <a href="https://www.instagram.com/myclinic">ig</a>
    <a href="https://www.linkedin.com/company/myclinic">li</a>
    """
    out = enrich_business_intelligence(html, "x.com")
    assert "facebook" in out["social_profiles"]
    assert "instagram" in out["social_profiles"]
    assert "linkedin" in out["social_profiles"]


def test_social_share_links_filtered():
    html = '<a href="https://www.facebook.com/sharer/sharer.php?u=x">share</a>'
    out = enrich_business_intelligence(html, "x.com")
    assert "facebook" not in out["social_profiles"]


def test_detect_tech_signals():
    html = """
    <script src="https://js.stripe.com/v3"></script>
    <script src="https://assets.calendly.com/x.js"></script>
    <a href="https://calendly.com/clinic">book</a>
    <script src="https://widget.intercom.io/widget/abc"></script>
    """
    out = enrich_business_intelligence(html, "x.com")
    assert "stripe" in out["tech_signals"]
    assert "calendly" in out["tech_signals"]
    assert "intercom" in out["tech_signals"]


def test_detect_founded_year():
    html = "<p>Serving patients since 2009. Quality care.</p>"
    out = enrich_business_intelligence(html, "x.com")
    assert out["founded_year"] == 2009
    assert out["years_in_business"] == datetime.utcnow().year - 2009


def test_founded_year_rejects_future():
    html = "<p>established 2999</p>"
    out = enrich_business_intelligence(html, "x.com")
    assert out["founded_year"] is None


def test_employee_range_explicit():
    html = "<p>Our team of 35 professionals is here for you.</p>"
    out = enrich_business_intelligence(html, "x.com")
    assert out["employee_range"] == "11-50"


def test_bi_score_increases_with_signals():
    poor = enrich_business_intelligence("<p>hello</p>", "x.com")
    rich = enrich_business_intelligence(
        """
        <a href="https://facebook.com/c">fb</a>
        <a href="https://instagram.com/c">ig</a>
        <script src="https://js.stripe.com/v3"></script>
        <a href="https://calendly.com/c">book</a>
        <p>Established 2005. Our team of 120 experts. Our locations nationwide.</p>
        """,
        "x.com",
    )
    assert rich["bi_score"] > poor["bi_score"]


def test_build_bi_summary_from_lead():
    lead = QualifiedLead(
        domain="x.com", location=None, niche="default", category=None, score=0.5,
        founded_year=2010, years_in_business=15, employee_range="11-50",
        location_count=3, tech_signals=["stripe", "calendly"],
        social_profiles=["facebook", "instagram"], revenue_tier="mid",
    )
    summary = build_bi_summary(lead)
    assert "2010" in summary
    assert "11-50" in summary
    assert summary.endswith(".")


def test_build_bi_summary_empty():
    lead = QualifiedLead(
        domain="x.com", location=None, niche="default", category=None, score=0.5,
    )
    assert build_bi_summary(lead) == "Limited public BI signals detected."
