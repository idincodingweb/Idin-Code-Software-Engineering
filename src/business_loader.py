from __future__ import annotations

from pathlib import Path

import yaml

from src.business_models import BusinessIntelTarget


class TargetLoaderError(ValueError):
    pass


class BusinessTargetLoader:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[BusinessIntelTarget]:
        if not self.path.exists():
            raise TargetLoaderError(f"Targets file not found: {self.path}")

        payload = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        raw_targets = payload.get("targets")
        if not isinstance(raw_targets, list):
            raise TargetLoaderError("targets.yaml must contain a top-level 'targets' list")

        targets: list[BusinessIntelTarget] = []
        seen: set[str] = set()

        for item in raw_targets:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain", "")).strip().lower()
            if not domain:
                continue
            if domain in seen:
                continue
            seen.add(domain)
            targets.append(
                BusinessIntelTarget(
                    domain=domain,
                    brand=str(item.get("brand", "")).strip(),
                    tier=_coerce_tier(item.get("tier", 3)),
                    location=str(item.get("location", "")).strip(),
                    niche=str(item.get("niche", "")).strip(),
                    category=str(item.get("category", "")).strip(),
                    notes=str(item.get("notes", "")).strip(),
                )
            )
        return targets


def _coerce_tier(value: object) -> int:
    try:
        tier = int(value)
    except (TypeError, ValueError):
        return 3
    return min(max(tier, 1), 3)
