# tests/test_extras.py
"""Unit tests untuk src/extras.py — zero-budget enrichment add-ons."""
from __future__ import annotations

from src.extras import (
    extract_emails_from_html,
    estimate_revenue_tier,
    _normalize_domain,
    _derive_business_name,
)


def test_extract_emails_basic():
    html = "<p>contact: john@clinic.com or info@clinic.com</p>"
    out = extract_emails_from_html(html)
    assert "john@clinic.com" in out
    assert "info@clinic.com" in out


def test_extract_emails_html_entity():
    html = "Email us at jane&#64;example-clinic.com"
    out = extract_emails_from_html(html)
    assert "jane@example-clinic.com" in out


def test_extract_emails_filters_noise():
    html = "logo@2x.png and a@example.com and real@dental-co.com"
    out = extract_emails_from_html(html)
    assert "real@dental-co.com" in out
    assert "logo@2x.png" not in out
    assert "a@example.com" not in out


def test_extract_emails_empty():
    assert extract_emails_from_html("") == []
    assert extract_emails_from_html("no emails here") == []


def test_revenue_estimation_micro():
    html = "<html><body><p>Welcome to my clinic. Call 555-1234</p></body></html>"
    tier, score = estimate_revenue_tier(html, "tiny.com")
    assert tier in ("micro", "small")
    assert score <= 2


def test_revenue_estimation_enterprise():
    html = (
        "<html><body>"
        "<a href='/locations'>Our locations</a> across the country, "
        "featured in major publications. "
        "Careers — we're hiring nationwide. "
        "Visit our branches: +1 555-0001, +1 555-0002, +1 555-0003, "
        "+1 555-0004, +1 555-0005, +1 555-0006. "
        "Blog | Articles | News | Insights"
        "</body></html>"
    )
    tier, score = estimate_revenue_tier(html, "big.com")
    assert score >= 4


def test_revenue_empty():
    tier, score = estimate_revenue_tier("", "x.com")
    assert tier == "unknown"
    assert score == 0


def test_normalize_domain():
    assert _normalize_domain("https://www.foo.com/bar") == "foo.com"
    assert _normalize_domain("HTTP://Foo.Com") == "foo.com"
    assert _normalize_domain("bar.com") == "bar.com"


def test_derive_business_name():
    assert _derive_business_name("drsmiledental.com") == "drsmiledental"
    assert _derive_business_name("www.acme.io") == "acme"
