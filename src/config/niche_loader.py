# src/config/niche_loader.py
"""Load per-niche YAML config for analyst + quality scoring.

Design goals:
- ganti `targets.yaml` saja, code tetap sama
- fallback ke `default.yaml` kalau niche belum punya config
- normalize schema agar caller bisa simpel
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
    slug = _safe_slug(niche)
    return NICHE_CONFIG_DIR / f"{slug}.yaml"


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
    scoring = raw.get("quality_score") or {}
    analyst = raw.get("analyst") or {}

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
                    "If the business already looks operationally mature, lower urgency and mention limited opportunity.",
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
            "base": int(scoring.get("base", 50)),
            "rules": list(scoring.get("rules") or []),
        },
    }


@lru_cache(maxsize=128)
def load_niche_config(niche: str) -> dict[str, Any]:
    niche_slug = _safe_slug(niche or DEFAULT_NICHE_CONFIG)
    default_path = _config_path_for(DEFAULT_NICHE_CONFIG)

    if not default_path.exists():
        raise FileNotFoundError(
            f"Default niche config not found: {default_path}"
        )

    with default_path.open("r", encoding="utf-8") as f:
        default_raw = yaml.safe_load(f) or {}

    config_path = _config_path_for(niche_slug)
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            niche_raw = yaml.safe_load(f) or {}
    else:
        niche_raw = {}

    merged = _deep_merge(default_raw, niche_raw)
    return _normalize_config(merged, niche_slug)
