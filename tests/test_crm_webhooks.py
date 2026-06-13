# tests/test_crm_webhooks.py
"""Unit tests untuk src/crm_webhooks.py — CRM webhook dispatcher.

Semua test ini OFFLINE: gak ada network call beneran (pakai env kosong /
dry_run). Logika config parsing + payload formatting yang dites.
"""
from __future__ import annotations

import asyncio

from src.crm_webhooks import (
    load_crm_targets,
    crm_configured,
    format_payload,
    push_leads_to_crm,
)
from src.models import QualifiedLead


def _lead(**kw) -> QualifiedLead:
    base = dict(domain="clinic.com", location="NYC", niche="medspa",
                category=None, score=0.82)
    base.update(kw)
    return QualifiedLead(**base)


def test_load_crm_targets_empty():
    assert load_crm_targets({}) == []
    assert crm_configured({}) is False


def test_load_crm_targets_single():
    env = {"CRM_HUBSPOT_WEBHOOK_URL": "https://hooks.example.com/hs"}
    targets = load_crm_targets(env)
    assert targets == [("hubspot", "https://hooks.example.com/hs")]
    assert crm_configured(env) is True


def test_load_crm_targets_generic_multi():
    env = {"CRM_GENERIC_WEBHOOK_URL": "https://a.com/1, https://b.com/2"}
    targets = load_crm_targets(env)
    assert ("generic", "https://a.com/1") in targets
    assert ("generic", "https://b.com/2") in targets
    assert len(targets) == 2


def test_format_payload_generic():
    lead = _lead(emails_found=["owner@clinic.com"], quality_score=88)
    payload = format_payload("hubspot", lead)
    assert payload["provider"] == "hubspot"
    assert payload["source"] == "idincode-researche"
    assert payload["lead"]["domain"] == "clinic.com"
    assert payload["lead"]["primary_email"] == "owner@clinic.com"
    assert payload["lead"]["quality_score"] == 88


def test_format_payload_airtable():
    lead = _lead(quality_score=70)
    payload = format_payload("airtable", lead)
    assert "records" in payload
    assert payload["records"][0]["fields"]["domain"] == "clinic.com"
    assert payload["records"][0]["fields"]["quality_score"] == 70


def test_push_no_config_skips():
    leads = [_lead()]
    summary = asyncio.run(push_leads_to_crm(leads, env={}))
    assert summary["sent"] == 0
    assert summary["skipped_reason"] is not None
    assert "no CRM webhook configured" in summary["skipped_reason"]


def test_push_filters_by_min_score():
    leads = [_lead(score=0.9), _lead(domain="low.com", score=0.4)]
    env = {"CRM_GENERIC_WEBHOOK_URL": "https://x.com/h"}
    summary = asyncio.run(
        push_leads_to_crm(leads, min_score=0.7, dry_run=True, env=env)
    )
    assert summary["selected"] == 1
    assert summary["dry_run"] is True
    assert summary["sent"] == 0  # dry-run never sends


def test_push_dry_run_no_send():
    leads = [_lead(score=0.95)]
    env = {"CRM_HUBSPOT_WEBHOOK_URL": "https://x.com/h"}
    summary = asyncio.run(push_leads_to_crm(leads, dry_run=True, env=env))
    assert summary["selected"] == 1
    assert summary["endpoints"] == 1
    assert summary["sent"] == 0
    assert summary["failed"] == 0
