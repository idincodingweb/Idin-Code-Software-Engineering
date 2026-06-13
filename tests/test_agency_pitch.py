"""Tests for agency-pitch email pipeline (v3.3+)."""
from __future__ import annotations

import asyncio
import csv
import os
from pathlib import Path

# Force IDINCODE_API empty so we always exercise the fallback template
# (deterministic, no network).
os.environ.pop("IDINCODE_API", None)

from src.email_generator import (
    generate_emails_for_agency_pitch,
    _fallback_agency_pitch,
)


class _P:
    def __init__(self, name, title, email):
        self.name, self.title, self.email = name, title, email


class _L:
    def __init__(self, persons, **kw):
        self.persons = persons
        self.agency_domain = kw.get("agency_domain", "agency.com")
        self.agency_name = kw.get("agency_name", "Agency LLC")
        self.niche_keyword = kw.get("niche_keyword", "medspa marketing")
        self.country = kw.get("country", "US")


def test_fallback_agency_pitch_shape():
    r = {
        "first_name": "Jane",
        "agency_name": "Bright Agency",
        "niche_keyword": "medspa marketing",
    }
    out = _fallback_agency_pitch(r, {"niche": "medspa", "count": 10})
    assert out["subject"] and "feedback" in out["subject"].lower()
    assert "Jane" in out["body"]
    assert "medspa" in out["body"]
    assert out["cta"]


def test_fallback_agency_pitch_no_first_name():
    r = {"first_name": "", "agency_name": "X", "niche_keyword": "y"}
    out = _fallback_agency_pitch(r, None)
    assert "Hi there" in out["body"]


def test_generate_emails_for_agency_pitch_no_api_uses_fallback():
    leads = [_L([_P("Jane Doe", "CEO", "jane@agency.com")])]
    out = asyncio.run(generate_emails_for_agency_pitch(
        leads, sample_summary={"niche": "medspa", "count": 8}
    ))
    key = "agency.com|jane@agency.com"
    assert key in out
    assert out[key]["subject"]
    assert "Jane" in out[key]["body"]


def test_generate_emails_for_agency_pitch_skips_no_email():
    leads = [_L([_P("Nobody", "Owner", "")])]
    out = asyncio.run(generate_emails_for_agency_pitch(leads))
    assert out == {}


def test_agency_buyers_csv_reader(tmp_path):
    """generate_emails.read_agency_buyers_csv normalizes website->domain."""
    # avoid sys.path tricks: import the script module by path
    import sys
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen_emails_mod",
        str(Path(__file__).resolve().parents[1] / "generate_emails.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["gen_emails_mod"] = mod
    spec.loader.exec_module(mod)

    csv_path = tmp_path / "agency_buyers_latest.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "website", "agency_name", "niche_keyword", "country",
            "ceo_name", "ceo_title", "email",
        ])
        w.writeheader()
        w.writerow({
            "website": "https://www.BrightAgency.com/about",
            "agency_name": "Bright Agency",
            "niche_keyword": "medspa marketing",
            "country": "US",
            "ceo_name": "Jane Doe",
            "ceo_title": "Founder",
            "email": "jane@brightagency.com",
        })
        # row with no email -> skipped
        w.writerow({
            "website": "https://noemail.com",
            "agency_name": "NoEmail",
            "niche_keyword": "x", "country": "US",
            "ceo_name": "", "ceo_title": "", "email": "",
        })

    leads = mod.read_agency_buyers_csv(str(csv_path), limit=None)
    assert len(leads) == 1
    l = leads[0]
    assert l.agency_domain == "brightagency.com"
    assert l.agency_name == "Bright Agency"
    assert l.persons[0].email == "jane@brightagency.com"
    assert l.persons[0].title == "Founder"
