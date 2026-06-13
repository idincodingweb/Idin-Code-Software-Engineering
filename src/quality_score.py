# src/quality_score.py
"""Lead Quality Score (0-100).

Roadmap v3.4: ganti dari heuristic 0-1 (gold_score) ke skala 0-100 yang
lebih kaya. gold_score (0-1) TETEP ADA & TETEP dipakai buat tiering/sorting —
quality_score ini LAYER TAMBAHAN yang nge-blend opportunity (gold_score)
dengan sinyal contactability + buying signals dari extras.

Dua jalur:
    1. compute_quality_score(lead)  -> deterministic 0-100 (SELALU dihitung di
       qualifier, jadi CSV selalu keisi walau AI mati).
    2. analyst.py boleh OVERRIDE pakai angka AI 0-100 kalau IDINCODE_API ada
       (lihat src/analyst.py). Kalau AI gagal/kosong → tetep pakai angka
       deterministic ini (graceful fallback, sesuai aturan main).

Arah skor: makin TINGGI = makin bagus lead-nya buat dijual
(opportunity gede + bisa dikontak + ada sinyal budget).
"""
from __future__ import annotations

from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_quality_score(lead: Any) -> int:
    """Hitung skor kualitas lead 0-100 (deterministic).

    Blend:
        - Base opportunity   : gold_score (0..1) -> 0..100
        - Contactability     : ada email scraped (+8), MX valid (+4 / -4)
        - Buying signals     : lagi pasang Meta Ads (+6)
        - Revenue sweet spot : small/mid (+5), large/enterprise (+2), micro (-3)

    Return: int 0..100 (clamped).
    """
    base = _as_float(getattr(lead, "score", 0.0)) * 100.0
    score = base

    # --- Contactability: lead yang gak bisa dikontak susah dijual ---
    if getattr(lead, "emails_found", None):
        score += 8.0

    mx_valid = getattr(lead, "mx_valid", None)
    if mx_valid is True:
        score += 4.0
    elif mx_valid is False:
        score -= 4.0

    # --- Buying signal: lagi spend di Meta = ada budget marketing ---
    if getattr(lead, "running_meta_ads", None) is True:
        score += 6.0

    # --- Revenue band sweet spot ---
    tier = (getattr(lead, "revenue_tier", "") or "").lower()
    if tier in ("small", "mid"):
        score += 5.0
    elif tier in ("large", "enterprise"):
        score += 2.0
    elif tier == "micro":
        score -= 3.0

    # --- Business sophistication (BI) nambah confidence dikit ---
    bi_score = _as_float(getattr(lead, "bi_score", 0))
    if bi_score >= 60:
        score += 3.0
    elif bi_score >= 30:
        score += 1.0

    return _clamp_int(score)


def _clamp_int(value: float) -> int:
    return max(0, min(100, int(round(value))))


def quality_band(score: int) -> str:
    """Label band untuk readability (dipakai di PDF/summary kalau perlu)."""
    if score >= 80:
        return "A (hot)"
    if score >= 65:
        return "B (warm)"
    if score >= 45:
        return "C (lukewarm)"
    return "D (cold)"


def sanitize_ai_quality_score(value: Any) -> int | None:
    """Validasi angka quality_score dari AI. Return int 0..100 atau None
    kalau gak valid (biar caller fallback ke deterministic)."""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    return _clamp_int(num)
