# src/loader.py
"""Load targets dari targets.yaml dengan validasi."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.models import Target


REQUIRED_FIELDS = ("domain", "location", "niche", "category")


def load_targets(yaml_path: str | Path = "targets.yaml") -> list[Target]:
    """Load & validate targets dari YAML file.

    Raises:
        FileNotFoundError: kalau YAML gak ada.
        ValueError: kalau struktur YAML salah / missing fields.
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(
            f"targets.yaml tidak ditemukan di {path.absolute()}. "
            f"Buat dulu file targets.yaml di root project."
        )

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(
            f"targets.yaml harus dict di top-level, dapat {type(raw).__name__}"
        )

    targets_raw = raw.get("targets")
    if not isinstance(targets_raw, list):
        raise ValueError(
            "targets.yaml harus punya key 'targets' yang berisi list."
        )

    if not targets_raw:
        raise ValueError("targets.yaml kosong - minimal harus ada 1 target.")

    targets: list[Target] = []
    for idx, item in enumerate(targets_raw):
        if not isinstance(item, dict):
            raise ValueError(
                f"Target index {idx} bukan dict (dapat {type(item).__name__})"
            )

        missing = [field for field in REQUIRED_FIELDS if field not in item or not item[field]]
        if missing:
            raise ValueError(
                f"Target index {idx} (domain={item.get('domain', '?')}) "
                f"missing field: {', '.join(missing)}"
            )

        domain = _normalize_domain(item["domain"])
        location = str(item["location"]).strip()
        niche = str(item["niche"]).strip().lower()
        category = str(item["category"]).strip()

        brand_raw = item.get("brand")
        brand = str(brand_raw).strip() if brand_raw is not None and str(brand_raw).strip() else None

        notes_raw = item.get("notes")
        notes = str(notes_raw).strip() if notes_raw is not None and str(notes_raw).strip() else None

        tier = _parse_tier(item.get("tier"), idx=idx, domain=domain)

        targets.append(
            Target(
                domain=domain,
                location=location,
                niche=niche,
                category=category,
                brand=brand,
                tier=tier,
                notes=notes,
            )
        )

    return targets


def _parse_tier(raw: Any, *, idx: int, domain: str) -> int | None:
    """Parse optional tier ke int kalau ada."""
    if raw is None or raw == "":
        return None

    try:
        tier = int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"Target index {idx} (domain={domain}) punya tier invalid: {raw!r}"
        ) from e

    if tier < 1:
        raise ValueError(
            f"Target index {idx} (domain={domain}) punya tier invalid: {tier}. "
            "tier harus >= 1."
        )
    return tier


def _normalize_domain(raw: Any) -> str:
    """Strip protocol, www, path, query, dan trailing slash dari domain."""
    value = str(raw).strip().lower()
    value = value.removeprefix("https://").removeprefix("http://")
    value = value.removeprefix("www.")

    value = value.split("/", 1)[0]
    value = value.split("?", 1)[0]
    value = value.split("#", 1)[0]
    value = value.rstrip("/")

    if not value:
        raise ValueError("domain kosong setelah normalisasi")

    return value
