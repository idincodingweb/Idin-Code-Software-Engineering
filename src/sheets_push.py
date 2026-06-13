# src/sheets_push.py
"""Google Sheets push — kirim hasil CSV ke spreadsheet online (gratis).

Pake gspread + Google Service Account (gratis tis tis, kuota personal).

Cara setup (one-time):
    1. Buat project di https://console.cloud.google.com (gratis)
    2. Enable "Google Sheets API" + "Google Drive API"
    3. Buat Service Account, download JSON key
    4. Share spreadsheet target ke email service account (xxx@xxx.iam.gserviceaccount.com)
    5. Set env:
         GOOGLE_SERVICE_ACCOUNT_JSON      = /path/to/key.json
         GSHEET_SPREADSHEET_ID            = abcdef123... (dari URL)
       Atau (alternatif):
         GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT = '{"type":"service_account",...}'
         GSHEET_SPREADSHEET_NAME          = "Idincode Leads"

Pipeline kompatibel: GRACEFUL-FAIL. Kalau gspread gak ke-install / JSON gak
ada / spreadsheet gak diakses → print warning, return summary, JANGAN crash.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Optional

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")
GSHEET_SPREADSHEET_ID = os.getenv("GSHEET_SPREADSHEET_ID", "")
GSHEET_SPREADSHEET_NAME = os.getenv("GSHEET_SPREADSHEET_NAME", "")

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _load_credentials():
    """Lazy-load gspread + creds. Return (client, error_str)."""
    try:
        import gspread  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
    except ImportError as e:
        return None, f"missing_dependency:{e}. Run: pip install gspread google-auth"

    info: Optional[dict] = None
    if GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT:
        try:
            info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT)
        except json.JSONDecodeError as e:
            return None, f"bad_json_content:{e}"
    elif GOOGLE_SERVICE_ACCOUNT_JSON:
        p = Path(GOOGLE_SERVICE_ACCOUNT_JSON).expanduser()
        if not p.exists():
            return None, f"json_file_not_found:{p}"
        try:
            info = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return None, f"bad_json_file:{e}"
    else:
        return None, "no_credentials_configured (set GOOGLE_SERVICE_ACCOUNT_JSON)"

    try:
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        client = gspread.authorize(creds)
        return client, ""
    except Exception as e:  # noqa: BLE001
        return None, f"auth_failed:{type(e).__name__}:{e}"


def _open_spreadsheet(client, spreadsheet_id: str, spreadsheet_name: str):
    """Open by ID first, then by name. Return (spreadsheet, error_str)."""
    try:
        if spreadsheet_id:
            return client.open_by_key(spreadsheet_id), ""
        if spreadsheet_name:
            return client.open(spreadsheet_name), ""
    except Exception as e:  # noqa: BLE001
        return None, f"open_failed:{type(e).__name__}:{e}"
    return None, "no_spreadsheet_id_or_name"


def _read_csv(path: str) -> list[list[str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def _worksheet_name_for(path: str) -> str:
    """File 'leads_premium_gold.csv' → 'leads_premium_gold' (max 100 chars)."""
    stem = Path(path).stem
    return stem[:100] or "Sheet1"


def _upsert_worksheet(spreadsheet, name: str, rows: int, cols: int):
    """Get or create worksheet. Clear then resize to fit data."""
    try:
        ws = spreadsheet.worksheet(name)
        ws.clear()
        # Resize to fit
        try:
            ws.resize(rows=max(rows, 1), cols=max(cols, 1))
        except Exception:  # noqa: BLE001
            pass
        return ws
    except Exception:  # noqa: BLE001  (WorksheetNotFound or other)
        return spreadsheet.add_worksheet(
            title=name, rows=max(rows, 1), cols=max(cols, 1)
        )


def push_csvs_to_sheets(
    csv_paths: list[str],
    *,
    spreadsheet_id: Optional[str] = None,
    spreadsheet_name: Optional[str] = None,
) -> dict[str, Any]:
    """Push semua CSV ke spreadsheet. Tiap CSV → satu worksheet (nama = filename).

    Return summary dict:
        {
          "skipped_reason": "..." | None,
          "spreadsheet_url": "..." | None,
          "pushed": [{"file":..., "worksheet":..., "rows":N}, ...],
          "failed": [{"file":..., "error":...}, ...],
        }
    """
    summary: dict[str, Any] = {
        "skipped_reason": None,
        "spreadsheet_url": None,
        "pushed": [],
        "failed": [],
    }

    if not csv_paths:
        summary["skipped_reason"] = "no_csv_files"
        return summary

    sid = spreadsheet_id or GSHEET_SPREADSHEET_ID
    sname = spreadsheet_name or GSHEET_SPREADSHEET_NAME
    if not (sid or sname):
        summary["skipped_reason"] = (
            "no_spreadsheet_target (set GSHEET_SPREADSHEET_ID or GSHEET_SPREADSHEET_NAME)"
        )
        return summary

    client, err = _load_credentials()
    if not client:
        summary["skipped_reason"] = err
        return summary

    spreadsheet, err = _open_spreadsheet(client, sid, sname)
    if not spreadsheet:
        summary["skipped_reason"] = err
        return summary

    try:
        summary["spreadsheet_url"] = spreadsheet.url
    except Exception:  # noqa: BLE001
        pass

    for path in csv_paths:
        try:
            data = _read_csv(path)
            if not data:
                summary["failed"].append({"file": path, "error": "empty_or_missing"})
                continue
            ws_name = _worksheet_name_for(path)
            rows = len(data)
            cols = max((len(r) for r in data), default=1)
            ws = _upsert_worksheet(spreadsheet, ws_name, rows, cols)
            ws.update(range_name="A1", values=data, value_input_option="RAW")
            summary["pushed"].append({
                "file": path,
                "worksheet": ws_name,
                "rows": rows - 1 if rows > 1 else 0,  # exclude header
            })
            print(f"[sheets] OK {path} -> '{ws_name}' ({rows} rows)")
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}:{e}"
            summary["failed"].append({"file": path, "error": err})
            print(f"[sheets] FAIL {path}: {err}")

    return summary


__all__ = ["push_csvs_to_sheets"]