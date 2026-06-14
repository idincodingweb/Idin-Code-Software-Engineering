# src/quality_score.py
"""Lead Quality Score 0-100.

Config-driven per niche via YAML.
Kalau niche config tidak ada, otomatis fallback ke default.yaml.
"""
from __future__ import annotations

from typing import Any

from src.config.niche_loader import load_niche_config


def _to_number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _missing_tracking_count(lead: Any) -> int:
    count = 0
    if not getattr(lead, "meta_pixel_in_html", False):
        count += 1
    if not getattr(lead, "tiktok_pixel_in_html", False):
        count += 1
    if not getattr(lead, "ga4_in_html", False):
        count += 1
    if not getattr(lead, "gtm_in_html", False):
        count += 1
    if not getattr(lead, "google_ads_in_html", False):
        count += 1
    return count


def _field_value(lead: Any, field: str) -> Any:
    if field == "missing_tracking_count":
        return _missing_tracking_count(lead)
    if field == "social_profiles_count":
        return len(getattr(lead, "social_profiles", []) or [])
    if field == "emails_found_count":
        return len(getattr(lead, "emails_found", []) or [])
    return getattr(lead, field, None)


def _matches_condition(lead: Any, condition: dict[str, Any]) -> bool:
    field = str(condition.get("field", "")).strip()
    op = str(condition.get("op", "eq")).strip().lower()
    expected = condition.get("value")
    actual = _field_value(lead, field)

    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        values = expected if isinstance(expected, list) else [expected]
        return actual in values
    if op == "not_in":
        values = expected if isinstance(expected, list) else [expected]
        return actual not in values
    if op == "contains":
        if isinstance(actual, list):
            return expected in actual
        if isinstance(actual, str):
            return str(expected).lower() in actual.lower()
        return False
    if op == "truthy":
        return bool(actual)
    if op == "falsy":
        return not bool(actual)

    actual_num = _to_number(actual)
    expected_num = _to_number(expected)

    if op == "gte":
        return actual_num is not None and expected_num is not None and actual_num >= expected_num
    if op == "gt":
        return actual_num is not None and expected_num is not None and actual_num > expected_num
    if op == "lte":
        return actual_num is not None and expected_num is not None and actual_num <= expected_num
    if op == "lt":
        return actual_num is not None and expected_num is not None and actual_num < expected_num

    return False


def _matches_all(lead: Any, conditions: list[dict[str, Any]]) -> bool:
    return all(_matches_condition(lead, cond) for cond in conditions)


def _clamp_int(value: float) -> int:
    return max(0, min(100, int(round(value))))


def compute_quality_score(lead: Any) -> int:
    """Config-driven deterministic quality score 0..100."""
    niche = getattr(lead, "niche", "default") or "default"
    config = load_niche_config(niche)
    scoring = config["quality_score"]

    score = float(scoring.get("base", 55))

    # Gold score tetap dipakai sebagai anchor utama.
    base_gold = _to_number(getattr(lead, "score", 0.0)) or 0.0
    score += base_gold * 25.0

    for rule in scoring.get("rules", []):
        conditions = list(rule.get("conditions") or [])
        points = float(rule.get("points", 0))
        if conditions and _matches_all(lead, conditions):
            score += points

    return _clamp_int(score)


def quality_band(score: int) -> str:
    if score >= 80:
        return "A (hot)"
    if score >= 65:
        return "B (warm)"
    if score >= 45:
        return "C (lukewarm)"
    return "D (cold)"


def sanitize_ai_quality_score(value: Any) -> int | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:
        return None
    return _clamp_int(num)
