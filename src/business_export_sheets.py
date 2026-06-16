from __future__ import annotations

import json
import os
from typing import Iterable

import gspread
from google.oauth2.service_account import Credentials

from src.business_models import BusinessIntelLead

SCOPES = [
    &quot;https://www.googleapis.com/auth/spreadsheets&quot;,
    &quot;https://www.googleapis.com/auth/drive&quot;,
]


class BusinessSheetsExporter:
    def __init__(self, spreadsheet_id: str | None, title: str):
        self.spreadsheet_id = spreadsheet_id
        self.title = title
        self.client = self._build_client()

    def export(self, leads: Iterable[BusinessIntelLead]) -&gt; str:
        ordered = list(leads)
        rows = [lead.to_row() for lead in ordered]
        headers = list(rows[0].keys()) if rows else list(BusinessIntelLead().to_row().keys())

        if self.spreadsheet_id:
            workbook = self.client.open_by_key(self.spreadsheet_id)
        else:
            workbook = self.client.create(self.title)

        sheets = {
            &quot;business_intel_all&quot;: rows,
            &quot;business_intel_starter&quot;: [row for row in rows if row.get(&quot;business_score&quot;, 0) &gt;= 55],
            &quot;business_intel_pro&quot;: [row for row in rows if row.get(&quot;business_score&quot;, 0) &gt;= 70],
            &quot;business_intel_premium_gold&quot;: [row for row in rows if row.get(&quot;business_score&quot;, 0) &gt;= 85],
        }

        existing = {sheet.title: sheet for sheet in workbook.worksheets()}
        for sheet_name, sheet_rows in sheets.items():
            worksheet = existing.get(sheet_name)
            if worksheet is None:
                worksheet = workbook.add_worksheet(
                    title=sheet_name,
                    rows=max(100, len(sheet_rows) + 10),
                    cols=max(26, len(headers) + 2)
                )
            else:
                worksheet.clear()

            values = [headers] + [
                [row.get(header, &quot;&quot;) for header in headers]
                for row in sheet_rows
            ]
            worksheet.update(&quot;A1&quot;, values)
            worksheet.freeze(rows=1)

            try:
                worksheet.set_basic_filter()
            except Exception:
                pass

            self._resize_columns(worksheet, headers, sheet_rows)

        return workbook.id

    def _build_client(self) -&gt; gspread.Client:
        raw = os.getenv(&quot;GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT&quot;, &quot;&quot;).strip()
        if not raw:
            raise ValueError(&quot;GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT is required for Sheets export&quot;)
        info = json.loads(raw)
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(credentials)

    def _resize_columns(self, worksheet: gspread.Worksheet, headers: list[str], rows: list[dict]) -&gt; None:
        widths: list[dict] = []
        for index, header in enumerate(headers, start=1):
            content_lengths = [len(str(row.get(header, &quot;&quot;))) for row in rows[:200]]
            width = min(max([len(header)] + content_lengths) * 8 + 24, 420)
            widths.append({
                &quot;sheetId&quot;: worksheet.id,
                &quot;startIndex&quot;: index - 1,
                &quot;endIndex&quot;: index,
                &quot;pixelSize&quot;: width
            })

        worksheet.spreadsheet.batch_update({
            &quot;requests&quot;: [
                {
                    &quot;updateDimensionProperties&quot;: {
                        &quot;range&quot;: {
                            &quot;sheetId&quot;: worksheet.id,
                            &quot;dimension&quot;: &quot;COLUMNS&quot;,
                            &quot;startIndex&quot;: item[&quot;startIndex&quot;],
                            &quot;endIndex&quot;: item[&quot;endIndex&quot;]
                        },
                        &quot;properties&quot;: {&quot;pixelSize&quot;: item[&quot;pixelSize&quot;]},
                        &quot;fields&quot;: &quot;pixelSize&quot;,
                    }
                }
                for item in widths
            ]
        })
