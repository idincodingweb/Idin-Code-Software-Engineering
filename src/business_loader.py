from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

from src.business_models import BusinessIntelTarget


class TargetLoaderError(ValueError):
    pass


class BusinessTargetLoader:
    def __init__(self, path: Path):
        self.path = path

    def load(self):
        if not self.path.exists():
            raise TargetLoaderError("Targets file not found: " + str(self.path))

        try:
            payload = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise TargetLoaderError("Invalid YAML: " + str(exc)) from exc

        raw_targets = None
        if isinstance(payload, list):
            raw_targets = payload
        elif isinstance(payload, dict):
            for key in ("targets", "brands", "leads", "domains", "items"):
                if key in payload and isinstance(payload[key], list):
                    raw_targets = payload[key]
                    break

        if not raw_targets:
            keys_info = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
            raise TargetLoaderError(
                "targets.yaml must contain a list under targets/brands/leads/domains/items. Got: " + str(keys_info)
            )

        targets = []
        seen = set()
        skipped = 0

        for item in raw_targets:
            if isinstance(item, str):
                domain = _normalize_domain(item)
                if not domain or domain in seen:
                    skipped += 1
                    continue
                seen.add(domain)
                targets.append(BusinessIntelTarget(domain=domain, brand=domain))
                continue

            if not isinstance(item, dict):
                skipped += 1
                continue

            raw_domain = (
                item.get("domain")
                or item.get("url")
                or item.get("website")
                or item.get("site")
                or item.get("homepage")
                or ""
            )
            domain = _normalize_domain(str(raw_domain))

            if not domain or domain in seen:
                skipped += 1
                continue
            seen.add(domain)

            targets.append(
                BusinessIntelTarget(
                    domain=domain,
                    brand=str(item.get("brand") or item.get("name") or domain).strip(),
                    tier=_coerce_tier(item.get("tier", 3)),
                    location=str(item.get("location") or item.get("country") or "").strip(),
                    niche=str(item.get("niche") or item.get("industry") or "").strip(),
                    category=str(item.get("category") or item.get("segment") or "").strip(),
                    notes=str(item.get("notes") or item.get("note") or "").strip(),
                )
            )

        print("Loaded " + str(len(targets)) + " targets (skipped: " + str(skipped) + ")")
        if not targets:
            raise TargetLoaderError("No valid targets found. Each item needs a domain/url/website field.")
        return targets


def _normalize_domain(value: str) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    if "://" in value:
        parsed = urlparse(value)
        value = parsed.netloc or parsed.path
    value = re.sub(r"^www\.", "", value)
    value = value.split("/")[0].split("?")[0].strip()
    return value


def _coerce_tier(value) -> int:
    try:
        tier = int(value)
    except (TypeError, ValueError):
        return 3
    return min(max(tier, 1), 3)
