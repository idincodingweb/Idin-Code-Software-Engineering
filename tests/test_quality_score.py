# tests/test_quality_score.py
"""Unit tests untuk src/quality_score.py — Lead Quality Score 0-100."""
from __future__ import annotations

from src.models import QualifiedLead
from src.quality_score import (
    compute_quality_score,
    quality_band,
    sanitize_ai_quality_score,
)


def _lead(**kw) -> QualifiedLead:
    base = dict(domain="x.com", location=None, niche="default", category=None, score=0.5)
    base.update(kw)
    return QualifiedLead(**base)


def test_quality_score_in_range():
    lead = _lead(score=0.0)
    assert compute_quality_score(lead) == 0
    lead = _lead(score=1.0)
    assert compute_quality_score(lead) <= 100


def test_quality_score_base_from_gold():
    lead = _lead(score=0.6)
    # base 60, no other signals -> 60
    assert compute_quality_score(lead) == 60


def test_quality_score_contactability_bonus():
    no_contact = _lead(score=0.5)
    with_contact = _lead(score=0.5, emails_found=["owner@x.com"], mx_valid=True)
    assert compute_quality_score(with_contact) > compute_quality_score(no_contact)


def test_quality_score_mx_invalid_penalty():
    lead = _lead(score=0.5, mx_valid=False)
    assert compute_quality_score(lead) == 46  # 50 - 4


def test_quality_score_buying_signal():
    lead = _lead(score=0.5, running_meta_ads=True)
    assert compute_quality_score(lead) == 56  # 50 + 6


def test_quality_score_revenue_sweetspot():
    micro = _lead(score=0.5, revenue_tier="micro")
    mid = _lead(score=0.5, revenue_tier="mid")
    assert compute_quality_score(micro) == 47  # 50 - 3
    assert compute_quality_score(mid) == 55     # 50 + 5


def test_quality_score_clamped_top():
    lead = _lead(
        score=1.0, emails_found=["a@x.com"], mx_valid=True,
        running_meta_ads=True, revenue_tier="mid", bi_score=80,
    )
    assert compute_quality_score(lead) == 100


def test_sanitize_ai_quality_score():
    assert sanitize_ai_quality_score(72) == 72
    assert sanitize_ai_quality_score("85") == 85
    assert sanitize_ai_quality_score(150) == 100
    assert sanitize_ai_quality_score(-5) == 0
    assert sanitize_ai_quality_score(None) is None
    assert sanitize_ai_quality_score("not-a-number") is None


def test_quality_band():
    assert quality_band(90).startswith("A")
    assert quality_band(70).startswith("B")
    assert quality_band(50).startswith("C")
    assert quality_band(10).startswith("D")
