from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from src.business_models import BusinessIntelLead


class BusinessCsvExporter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, leads: Iterable[BusinessIntelLead]) -&gt; dict[str, Path]:
        ordered = list(leads)
        rows = [lead.to_row() for lead in ordered]
        headers = list(rows[0].keys()) if rows else self._headers()

        all_path = self.output_dir / &quot;business_intel_all.csv&quot;
        starter_path = self.output_dir / &quot;business_intel_starter.csv&quot;
        pro_path = self.output_dir / &quot;business_intel_pro.csv&quot;
        premium_path = self.output_dir / &quot;business_intel_premium_gold.csv&quot;

        self._write_csv(all_path, headers, rows)
        self._write_csv(starter_path, headers, [row for row in rows if row.get(&quot;business_score&quot;, 0) &gt;= 55])
        self._write_csv(pro_path, headers, [row for row in rows if row.get(&quot;business_score&quot;, 0) &gt;= 70])
        self._write_csv(premium_path, headers, [row for row in rows if row.get(&quot;business_score&quot;, 0) &gt;= 85])

        return {
            &quot;all&quot;: all_path,
            &quot;starter&quot;: starter_path,
            &quot;pro&quot;: pro_path,
            &quot;premium_gold&quot;: premium_path,
        }

    def _write_csv(self, path: Path, headers: list[str], rows: list[dict]) -&gt; None:
        with path.open(&quot;w&quot;, newline=&quot;&quot;, encoding=&quot;utf-8&quot;) as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def _headers(self) -&gt; list[str]:
        return list(BusinessIntelLead().to_row().keys())
