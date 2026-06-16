# src/export_sheets.py
"""Export qualified leads ke Google Sheets rapi (bukan CSV).

Butuh Google Service Account JSON di env var:
GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT (raw JSON content)

Output: 4 sheet (leads_all, leads_starter, leads_pro, leads_premium_gold)
dengan formatting rapi (header bold, auto-width, filter, conditional formatting).
"""
import json
import gspread
from google.oauth2.service_account import Credentials
from src.config import OUTPUT_DIR
from src.models import QualifiedLead


_SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

_HEADER_ROW = [
    "rank", "domain", "brand", "tier", "location", "niche", "category", "notes",
    "gold_score", "quality_score", "data_confidence", "pixel_confidence",
    "firmographics_confidence", "pixel_detection_method", "firmographics_source",
    "detection_notes", "data_quality_flags",
    "platform", "meta_pixel", "tiktok_pixel", "ga4", "gtm", "google_ads",
    "pagespeed_mobile", "lcp_ms", "response_ms", "revenue_tier", "revenue_score",
    "emails_found", "mx_valid", "email_status", "email_verification_method",
    "running_meta_ads", "meta_ads_count", "competitors",
    "bi_score", "employee_range", "location_count", "founded_year",
    "social_profiles", "tech_signals", "marketplaces",
    "gold_reasons", "outreach_angle", "bi_summary",
]

_TIER_CONFIGS = [
    {"name": "leads_all", "min_score": 0.0, "label": "All Leads"},
    {"name": "leads_starter", "min_score": 0.30, "label": "Starter Tier (≥0.30)"},
    {"name": "leads_pro", "min_score": 0.50, "label": "Pro Tier (≥0.50)"},
    {"name": "leads_premium_gold", "min_score": 0.70, "label": "Premium Gold Tier (≥0.70)"},
]


def _get_sheets_client() -> gspread.Client:
    """Auth ke Google Sheets via service account."""
    import os
    
    json_content = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
    if not json_content:
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT env var tidak diset. "
            "Download JSON dari Google Cloud Console &gt; Service Accounts."
        )
    
    creds_dict = json.loads(json_content)
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    return gspread.authorize(creds)


def _format_sheet(worksheet, data: list[list]) -> None:
    """Format Google Sheet: header tebal, auto-width, filter, conditional formatting."""
    if not data:
        return
    
    # Header format: bold + background color
    header_format = {
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "backgroundColor": {"red": 0.2, "green": 0.3, "blue": 0.4},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    }
    worksheet.format(f"A1:{_col_letter(len(data[0]))}1", [header_format] * len(data[0]))
    
    # Freeze header
    worksheet.freeze_rows(1)
    
    # Auto-width columns (gspread doesn't have auto-resize, tapi kita set ke reasonable default)
    for col_idx in range(1, len(data[0]) + 1):
        worksheet.set_column_width(col_idx, 150)  # Default 150px, user bisa resize
    
    # Add filter view
    if len(data) &gt; 1:
        try:
            worksheet.add_filter(f"A1:{_col_letter(len(data[0]))}{len(data)}")
        except:
            pass  # Kalau filter gagal, continue saja


def _col_letter(col_num: int) -> str:
    """Convert column number (1-indexed) ke letter (A, B, C, ..., Z, AA, AB, ...).
    
    Examples:
        1 -&gt; 'A'
        26 -&gt; 'Z'
        27 -&gt; 'AA'
        702 -&gt; 'ZZ'
    """
    letters = ""
    while col_num &gt; 0:
        col_num, remainder = divmod(col_num - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def export_to_sheets(
    leads: list[QualifiedLead],
    spreadsheet_id: str = "",
    spreadsheet_name: str = "Idincode Research Results",
) -&gt; dict[str, str]:
    """Export leads ke Google Sheets (4 sheet tier) dengan formatting rapi.
    
    Args:
        leads: list QualifiedLead yang sudah di-score
        spreadsheet_id: Existing spreadsheet ID (kalau kosong, create baru)
        spreadsheet_name: Nama spreadsheet kalau create baru
    
    Returns:
        dict dengan info: {
            "spreadsheet_id": "...",
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/...",
            "sheets_created": ["leads_all", "leads_starter", ...],
        }
    """
    client = _get_sheets_client()
    
    sorted_leads = sorted(leads, key=lambda x: x.score, reverse=True)
    for idx, lead in enumerate(sorted_leads, start=1):
        lead.rank = idx
    
    # Create atau open spreadsheet
    if spreadsheet_id:
        sheet = client.open_by_key(spreadsheet_id)
        print(f"[sheets] Opening existing spreadsheet: {spreadsheet_id}")
        # Clear existing sheets (except first)
        for ws in sheet.worksheets()[1:]:
            sheet.del_worksheet(ws)
    else:
        sheet = client.create(spreadsheet_name)
        print(f"[sheets] Created new spreadsheet: {sheet.id}")
    
    sheets_created = []
    
    for tier_cfg in _TIER_CONFIGS:
        filtered = [lead for lead in sorted_leads if lead.score &gt;= tier_cfg["min_score"]]
        filtered = filtered[:100]  # Limit per sheet (Google Sheets bisa slow kalau terlalu banyak row)
        
        # Convert leads to rows
        rows = [_HEADER_ROW]
        for lead in filtered:
            row = [
                getattr(lead, "rank", 0),
                lead.domain,
                getattr(lead, "brand", "") or "",
                str(getattr(lead, "tier", "") if getattr(lead, "tier", None) is not None else ""),
                lead.location or "",
                lead.niche,
                lead.category or "",
                getattr(lead, "notes", "") or "",
                f"{lead.score:.4f}",
                int(getattr(lead, "quality_score", 0) or 0),
                getattr(lead, "data_confidence", "low") or "low",
                getattr(lead, "pixel_confidence", "low") or "low",
                getattr(lead, "firmographics_confidence", "low") or "low",
                getattr(lead, "pixel_detection_method", "html_regex") or "html_regex",
                getattr(lead, "firmographics_source", "free_enrichment") or "free_enrichment",
                getattr(lead, "detection_notes", "") or "",
                "; ".join(str(f) for f in getattr(lead, "data_quality_flags", [])) or "",
                lead.platform or "Unknown",
                "ya" if lead.meta_pixel_in_html else "tidak",
                "ya" if getattr(lead, "tiktok_pixel_in_html", False) else "tidak",
                "ya" if lead.ga4_in_html else "tidak",
                "ya" if lead.gtm_in_html else "tidak",
                "ya" if lead.google_ads_in_html else "tidak",
                str(lead.pagespeed_score) if lead.pagespeed_score is not None else "",
                str(lead.lcp_ms) if lead.lcp_ms is not None else "",
                str(lead.response_ms) if lead.response_ms is not None else "",
                getattr(lead, "revenue_tier", "") or "",
                getattr(lead, "revenue_score", 0) or 0,
                "; ".join(str(e) for e in getattr(lead, "emails_found", [])) or "",
                "valid" if getattr(lead, "mx_valid", None) is True else ("invalid" if getattr(lead, "mx_valid", None) is False else "unknown"),
                getattr(lead, "best_email_status", "unknown") or "unknown",
                getattr(lead, "email_verification_method", "none") or "none",
                "ya" if getattr(lead, "running_meta_ads", None) is True else ("tidak" if getattr(lead, "running_meta_ads", None) is False else "unknown"),
                str(getattr(lead, "meta_ads_count", "")) if getattr(lead, "meta_ads_count", None) is not None else "",
                "; ".join(str(c) for c in getattr(lead, "competitors", [])) or "",
                int(getattr(lead, "bi_score", 0) or 0),
                getattr(lead, "employee_range", "") or "",
                int(getattr(lead, "location_count", 0) or 0),
                str(getattr(lead, "founded_year", "")) if getattr(lead, "founded_year", None) is not None else "",
                "; ".join(str(s) for s in getattr(lead, "social_profiles", [])) or "",
                "; ".join(str(t) for t in getattr(lead, "tech_signals", [])) or "",
                "; ".join(str(m) for m in getattr(lead, "marketplaces", [])) or "",
                lead.gold_reasons or "",
                lead.outreach_angle or "",
                getattr(lead, "bi_summary", "") or "",
            ]
            rows.append(row)
        
        # Add atau update sheet
        try:
            ws = sheet.worksheet(tier_cfg["name"])
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title=tier_cfg["name"], rows=len(rows) + 10, cols=len(_HEADER_ROW))
        
        # Write data
        ws.update([rows], range_name=f"A1:{_col_letter(len(_HEADER_ROW))}{len(rows)}")
        _format_sheet(ws, rows)
        
        sheets_created.append(tier_cfg["name"])
        print(f"[sheets] Created/updated sheet: {tier_cfg['name']} ({len(rows)-1} leads)")
    
    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{sheet.id}/edit"
    
    return {
        "spreadsheet_id": sheet.id,
        "spreadsheet_url": spreadsheet_url,
        "sheets_created": sheets_created,
    }
