from __future__ import annotations

import csv
from pathlib import Path

from src.business_models import BusinessIntelLead


class BusinessCsvExporter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, leads):
        ordered = list(leads)
        rows = [lead.to_row() for lead in ordered]
        headers = list(rows[0].keys()) if rows else list(BusinessIntelLead().to_row().keys())

        all_path = self.output_dir / "business_intel_all.csv"
        starter_path = self.output_dir / "business_intel_starter.csv"
        pro_path = self.output_dir / "business_intel_pro.csv"
        premium_path = self.output_dir / "business_intel_premium_gold.csv"

        self._write_csv(all_path, headers, rows)
        self._write_csv(starter_path, headers, [r for r in rows if r.get("business_score", 0) >= 55])
        self._write_csv(pro_path, headers, [r for r in rows if r.get("business_score", 0) >= 70])
        self._write_csv(premium_path, headers, [r for r in rows if r.get("business_score", 0) >= 85])

        return {
            "all": all_path,
            "starter": starter_path,
            "pro": pro_path,
            "premium_gold": premium_path,
        }

    def _write_csv(self, path: Path, headers, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
