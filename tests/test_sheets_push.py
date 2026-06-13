# tests/test_sheets_push.py
"""Unit tests buat src/sheets_push.py.

gspread di-mock semua. Test verifies graceful-fail behavior + happy path.
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

from src import sheets_push as sp


def _write_csv(path: Path, rows):
    import csv
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)


def test_skipped_when_no_files(monkeypatch):
    monkeypatch.setattr(sp, "GSHEET_SPREADSHEET_ID", "abc")
    summary = sp.push_csvs_to_sheets([])
    assert summary["skipped_reason"] == "no_csv_files"


def test_skipped_when_no_target(monkeypatch, tmp_path):
    monkeypatch.setattr(sp, "GSHEET_SPREADSHEET_ID", "")
    monkeypatch.setattr(sp, "GSHEET_SPREADSHEET_NAME", "")
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    summary = sp.push_csvs_to_sheets([str(p)])
    assert "no_spreadsheet_target" in summary["skipped_reason"]


def test_skipped_when_no_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(sp, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setattr(sp, "GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")
    monkeypatch.setattr(sp, "GSHEET_SPREADSHEET_ID", "abc")
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    summary = sp.push_csvs_to_sheets([str(p)])
    assert "no_credentials_configured" in (summary["skipped_reason"] or "")


def test_skipped_when_json_file_missing(monkeypatch, tmp_path):
    bad_path = tmp_path / "nope.json"
    monkeypatch.setattr(sp, "GOOGLE_SERVICE_ACCOUNT_JSON", str(bad_path))
    monkeypatch.setattr(sp, "GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")
    monkeypatch.setattr(sp, "GSHEET_SPREADSHEET_ID", "abc")
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    summary = sp.push_csvs_to_sheets([str(p)])
    assert "json_file_not_found" in (summary["skipped_reason"] or "")


def test_happy_path_with_mocked_gspread(monkeypatch, tmp_path):
    p = tmp_path / "leads_pro.csv"
    _write_csv(p, [["domain", "score"], ["a.com", "0.9"], ["b.com", "0.8"]])

    fake_ws = mock.MagicMock()
    fake_ss = mock.MagicMock()
    fake_ss.url = "https://docs.google.com/spreadsheets/d/abc/edit"
    fake_ss.worksheet.side_effect = Exception("not found")  # force add_worksheet
    fake_ss.add_worksheet.return_value = fake_ws
    fake_client = mock.MagicMock()
    fake_client.open_by_key.return_value = fake_ss

    monkeypatch.setattr(sp, "_load_credentials", lambda: (fake_client, ""))
    monkeypatch.setattr(sp, "GSHEET_SPREADSHEET_ID", "abc")

    summary = sp.push_csvs_to_sheets([str(p)])
    assert summary["skipped_reason"] is None
    assert summary["spreadsheet_url"].endswith("/edit")
    assert len(summary["pushed"]) == 1
    assert summary["pushed"][0]["worksheet"] == "leads_pro"
    assert summary["pushed"][0]["rows"] == 2  # excludes header
    fake_ws.update.assert_called_once()
    args, kwargs = fake_ws.update.call_args
    assert kwargs.get("range_name") == "A1"
    assert kwargs.get("values")[0] == ["domain", "score"]


def test_worksheet_reused_when_exists(monkeypatch, tmp_path):
    p = tmp_path / "leads_starter.csv"
    _write_csv(p, [["x"], ["1"]])

    fake_ws = mock.MagicMock()
    fake_ss = mock.MagicMock()
    fake_ss.url = "u"
    fake_ss.worksheet.return_value = fake_ws  # found → reuse
    fake_client = mock.MagicMock()
    fake_client.open_by_key.return_value = fake_ss

    monkeypatch.setattr(sp, "_load_credentials", lambda: (fake_client, ""))
    monkeypatch.setattr(sp, "GSHEET_SPREADSHEET_ID", "abc")

    summary = sp.push_csvs_to_sheets([str(p)])
    assert len(summary["pushed"]) == 1
    fake_ws.clear.assert_called_once()
    fake_ss.add_worksheet.assert_not_called()