# tests/test_agency_buyer.py
"""Unit tests untuk pipeline agency-buyer (web + reddit + phone)."""
from __future__ import annotations

from src.agency_buyer_finder import (
    AgencyBuyerLead,
    _rank_ceo,
    extract_phones_from_html,
    _normalize_phone,
)
from src.agency_buyer_export import (
    export_agency_buyers_csv,
    export_reddit_buyers_csv,
)
from src.agency_buyers_loader import load_agency_buyers
from src.reddit_scraper import (
    RedditBuyerLead,
    _first_email,
    _first_external_url,
    _looks_like_buyer,
)


# ---------------- Phone ----------------
def test_normalize_phone_intl():
    assert _normalize_phone("+1 (415) 555-1234") == "+14155551234"


def test_normalize_phone_too_short():
    assert _normalize_phone("123-45") == ""


def test_normalize_phone_too_long():
    assert _normalize_phone("12345678901234567890") == ""


def test_phone_extract_tel_href():
    html = '<a href="tel:+14155551234">call</a>'
    out = extract_phones_from_html(html)
    assert "+14155551234" in out


def test_phone_extract_text():
    html = "Call us at 415-555-1234 today"
    out = extract_phones_from_html(html)
    assert any("4155551234" in p.replace("-", "") for p in out)


def test_phone_extract_filters_repeated():
    html = "fake: 111-111-1111 real: 415-555-9876"
    out = extract_phones_from_html(html)
    digits = [p.replace("-", "").replace("+", "") for p in out]
    assert "1111111111" not in digits
    assert any("4155559876" in d for d in digits)


# ---------------- CEO rank ----------------
def test_rank_ceo_prefers_ceo():
    people = [("Jane Doe", "Partner"), ("John Roe", "CEO"), ("Sue Lee", "Director")]
    best = _rank_ceo(people)
    assert best == ("John Roe", "CEO")


def test_rank_ceo_founder_fallback():
    people = [("Jane Doe", "Partner"), ("John Roe", "Founder")]
    best = _rank_ceo(people)
    assert best == ("John Roe", "Founder")


def test_rank_ceo_none_strong():
    people = [("Jane Doe", "Director")]
    assert _rank_ceo(people) is None


# ---------------- Reddit ----------------
def test_reddit_indicators_match():
    txt = "Hey, I run a small agency doing dental SEO for clinics."
    hits = _looks_like_buyer(txt)
    assert hits  # at least one indicator

def test_reddit_no_match():
    assert _looks_like_buyer("just a regular post about coffee") == []


def test_reddit_first_email_url():
    txt = "Contact me at jane@example.com or visit https://my-agency.com"
    assert _first_email(txt) == "jane@example.com"
    assert _first_external_url(txt) == "https://my-agency.com"


def test_reddit_first_url_skips_social():
    txt = "see my linkedin https://linkedin.com/in/me and my site https://my-agency.com"
    assert _first_external_url(txt) == "https://my-agency.com"


# ---------------- Loader ----------------
def test_load_agency_buyers_default():
    cfg = load_agency_buyers("agency_buyers.yaml")
    assert cfg.niches, "expected at least 1 niche"
    assert cfg.max_agencies_per_niche > 0


# ---------------- Export smoke ----------------
def test_export_agency_buyers_empty(tmp_path):
    out = export_agency_buyers_csv([], output_dir=str(tmp_path))
    assert out and all(p.endswith(".csv") for p in out)


def test_export_reddit_buyers_empty(tmp_path):
    out = export_reddit_buyers_csv([], output_dir=str(tmp_path))
    assert out and all(p.endswith(".csv") for p in out)


def test_export_agency_buyers_rows(tmp_path):
    lead = AgencyBuyerLead(
        source="website",
        website="my-agency.com",
        agency_name="My Agency",
        niche_keyword="dental seo agency",
        country="US",
        email="jane@my-agency.com",
        phone="+14155551234",
        ceo_name="Jane Doe",
        ceo_title="Founder",
        ceo_source="heuristic",
        mx_valid=True,
    )
    out = export_agency_buyers_csv([lead], output_dir=str(tmp_path))
    txt = open(out[0]).read()
    assert "Jane Doe" in txt
    assert "+14155551234" in txt


def test_export_reddit_rows(tmp_path):
    lead = RedditBuyerLead(
        subreddit="SEO", author="agencyowner1",
        post_title="my dental seo agency", post_url="https://reddit.com/x",
        permalink="https://reddit.com/r/SEO/x",
        snippet="I run a small agency", website="https://my-agency.com",
        email="me@my-agency.com",
        matched_indicators="i run a small agency",
        score=42,
    )
    out = export_reddit_buyers_csv([lead], output_dir=str(tmp_path))
    txt = open(out[0]).read()
    assert "agencyowner1" in txt and "my-agency.com" in txt
