"""Unit tests for src/sample_pack.py — sample pack generator."""
from __future__ import annotations

import csv
import os
from pathlib import Path

from src.sample_pack import (
    build_sample_pack,
    _primary_issue,
    _problem_count,
    _first_email,
    _mx_status,
    SAMPLE_CSV_COLUMNS,
)


def _row(**kw) -> dict:
    base = {
        "domain": "example.com",
        "niche": "plastic_surgery",
        "location": "US",
        "gold_score": "0.90",
        "pagespeed_mobile": "55",
        "lcp_ms": "4200",
        "meta_pixel_in_html": "no",
        "ga4_in_html": "yes",
        "google_ads_in_html": "no",
        "platform": "WordPress",
        "emails_found": "info@example.com; ceo@example.com",
        "mx_valid": "valid",
        "outreach_angle": "fix slow LCP, add Meta pixel",
    }
    base.update(kw)
    return base


def test_primary_issue_priority_lcp_first():
    r = _row(lcp_ms="4000", pagespeed_mobile="40")
    assert "LCP" in _primary_issue(r)


def test_primary_issue_pagespeed_when_no_lcp():
    r = _row(lcp_ms="", pagespeed_mobile="35")
    assert "PageSpeed" in _primary_issue(r)


def test_primary_issue_missing_pixel():
    r = _row(lcp_ms="", pagespeed_mobile="80", meta_pixel_in_html="no")
    assert "Meta Pixel" in _primary_issue(r)


def test_problem_count_accumulates():
    r = _row(
        lcp_ms="5000", pagespeed_mobile="30",
        meta_pixel_in_html="no", ga4_in_html="no", google_ads_in_html="no",
    )
    # 2 (ps<60) + 2 (lcp>3500) + 1+1+1 (pixels)
    assert _problem_count(r) == 7


def test_first_email_picks_first():
    assert _first_email(_row()) == "info@example.com"
    assert _first_email({"emails_found": ""}) == ""


def test_mx_status_normalization():
    assert _mx_status({"mx_valid": "valid"}) == "verified"
    assert _mx_status({"mx_valid": "invalid"}) == "invalid"
    assert _mx_status({"mx_valid": ""}) == "unknown"


def test_build_sample_pack_writes_csv(tmp_path):
    rows = [_row(domain=f"d{i}.com", gold_score=f"0.{90-i}") for i in range(5)]
    out_dir = tmp_path / "sp"
    res = build_sample_pack(
        rows, niche_label="plastic_surgery",
        out_dir=str(out_dir), top_n=3, min_score=0.0,
    )
    assert res["count"] == 3
    assert res["csv"] and Path(res["csv"]).exists()
    with open(res["csv"], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == list(SAMPLE_CSV_COLUMNS)
        rows_out = list(reader)
    assert len(rows_out) == 3
    # rank starts at 1
    assert rows_out[0]["rank"] == "1"
    # highest score first
    assert rows_out[0]["domain"] == "d0.com"


def test_build_sample_pack_empty_input(tmp_path):
    res = build_sample_pack([], out_dir=str(tmp_path), top_n=5)
    assert res["count"] == 0
    assert res["csv"] is None


def test_build_sample_pack_min_score_fallback(tmp_path):
    # All rows have gold_score=0 -> filter would drop all, but builder
    # should fall back to using everything.
    rows = [_row(domain=f"x{i}.com", gold_score="0") for i in range(3)]
    res = build_sample_pack(
        rows, out_dir=str(tmp_path), top_n=2, min_score=0.5,
    )
    assert res["count"] == 2
    assert Path(res["csv"]).exists()


def test_build_sample_pack_pdf_optional(tmp_path):
    # PDF may or may not be generated depending on reportlab availability —
    # just ensure no crash either way and CSV always present.
    rows = [_row()]
    res = build_sample_pack(rows, out_dir=str(tmp_path), top_n=1, min_score=0.0)
    assert res["csv"] and os.path.exists(res["csv"])
