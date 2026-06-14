# src/config/niche_loader.py
"""Load per-niche YAML config for analyst + qualifier + quality scoring.

Goals:
- Ganti targets.yaml / niche tanpa ubah Python code.
- Fallback ke default.yaml kalau niche belum ada.
- Schema dinormalisasi supaya caller simpel.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config import DEFAULT_NICHE_CONFIG, NICHE_CONFIG_DIR


def _safe_slug(value: str) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _config_path_for(niche: str) -> Path:
    return NICHE_CONFIG_DIR / f"{_safe_slug(niche)}.yaml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_config(raw: dict[str, Any], niche: str) -> dict[str, Any]:
    metadata = raw.get("metadata") or {}
    analyst = raw.get("analyst") or {}
    quality_score = raw.get("quality_score") or {}
    qualifier = raw.get("qualifier") or {}

    weights = qualifier.get("weights") or {}
    total = (
        float(weights.get("pixels", 0.0))
        + float(weights.get("pagespeed", 0.0))
        + float(weights.get("lcp", 0.0))
        + float(weights.get("platform", 0.0))
    )
    if total <= 0:
        norm_weights = {
            "pixels": 0.40,
            "pagespeed": 0.30,
            "lcp": 0.15,
            "platform": 0.15,
        }
    else:
        norm_weights = {
            "pixels": float(weights.get("pixels", 0.0)) / total,
            "pagespeed": float(weights.get("pagespeed", 0.0)) / total,
            "lcp": float(weights.get("lcp", 0.0)) / total,
            "platform": float(weights.get("platform", 0.0)) / total,
        }

    return {
        "niche": niche,
        "metadata": {
            "industry_label": str(
                metadata.get("industry_label", "growth-stage businesses")
            ).strip(),
            "typical_ticket": str(
                metadata.get("typical_ticket", "$1,000-$10,000 per customer")
            ).strip(),
            "pain_point": str(
                metadata.get("pain_point", "marketing attribution and conversion gaps")
            ).strip(),
        },
        "analyst": {
            "focus": str(
                analyst.get(
                    "focus",
                    "Identify concrete sales opportunities from tracking, performance, and business signals.",
                )
            ).strip(),
            "mature_business_note": str(
                analyst.get(
                    "mature_business_note",
                    "If the business already looks operationally mature, reduce urgency and frame it as limited opportunity.",
                )
            ).strip(),
            "fallback_reasons_rules": list(
                analyst.get("fallback_reasons_rules") or []
            ),
            "fallback_outreach_rules": list(
                analyst.get("fallback_outreach_rules") or []
            ),
        },
        "quality_score": {
            "base": int(quality_score.get("base", 55)),
            "rules": list(quality_score.get("rules") or []),
        },
        "qualifier": {
            "weights": norm_weights,
            "response_penalty_threshold_ms": int(
                qualifier.get("response_penalty_threshold_ms", 2000)
            ),
            "response_penalty_factor": float(
                qualifier.get("response_penalty_factor", 0.15)
            ),
        },
    }


@lru_cache(maxsize=128)
def load_niche_config(niche: str) -> dict[str, Any]:
    niche_slug = _safe_slug(niche or DEFAULT_NICHE_CONFIG)
    default_path = _config_path_for(DEFAULT_NICHE_CONFIG)

    if not default_path.exists():
        raise FileNotFoundError(f"Default niche config not found: {default_path}")

    with default_path.open("r", encoding="utf-8") as f:
        default_raw = yaml.safe_load(f) or {}

    niche_path = _config_path_for(niche_slug)
    if niche_path.exists():
        with niche_path.open("r", encoding="utf-8") as f:
            niche_raw = yaml.safe_load(f) or {}
    else:
        niche_raw = {}

    merged = _deep_merge(default_raw, niche_raw)
    return _normalize_config(merged, niche_slug)
