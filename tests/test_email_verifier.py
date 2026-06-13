# tests/test_email_verifier.py
"""Unit tests buat src/email_verifier.py.

Semua test pakai mock — gak ada koneksi SMTP / HTTP beneran.
"""
from __future__ import annotations

from unittest import mock

import pytest

from src import email_verifier as ev


# ----------------------------- helpers -----------------------------
def test_is_valid_format():
    assert ev._is_valid_format("a@b.co")
    assert ev._is_valid_format("first.last+tag@sub.domain.io")
    assert not ev._is_valid_format("not-an-email")
    assert not ev._is_valid_format("")
    assert not ev._is_valid_format("a@b")


def test_best_status_ranking():
    assert ev.best_status([]) == "unknown"
    assert ev.best_status(["invalid", "unknown"]) == "unknown"
    assert ev.best_status(["invalid", "risky", "catch_all"]) == "catch_all"
    assert ev.best_status(["valid", "invalid", "risky"]) == "valid"
    assert ev.best_status(["invalid"]) == "invalid"


def test_is_deliverable():
    assert ev.is_deliverable("valid")
    assert ev.is_deliverable("catch_all")
    assert not ev.is_deliverable("invalid")
    assert not ev.is_deliverable("risky")
    assert not ev.is_deliverable("unknown")


# ----------------------------- SMTP RCPT -----------------------------
def _mock_smtp_factory(rcpt_code, rcpt_msg=b"ok", catch_all_code=550):
    """Build a MagicMock that mimics smtplib.SMTP context manager."""
    srv = mock.MagicMock()
    srv.ehlo_or_helo_if_needed.return_value = None
    srv.helo.return_value = (250, b"ok")
    srv.mail.return_value = (250, b"ok")

    call_count = {"n": 0}

    def rcpt(_email):
        call_count["n"] += 1
        # 1st call = real probe, 2nd = catch-all random
        if call_count["n"] == 1:
            return (rcpt_code, rcpt_msg)
        return (catch_all_code, b"x")

    srv.rcpt.side_effect = rcpt

    cm = mock.MagicMock()
    cm.__enter__.return_value = srv
    cm.__exit__.return_value = False
    return mock.MagicMock(return_value=cm)


def test_smtp_invalid_format():
    res = ev.verify_email_smtp("nope")
    assert res["status"] == "invalid"
    assert res["method"] == "smtp"


def test_smtp_disposable_domain():
    res = ev.verify_email_smtp("foo@mailinator.com")
    assert res["status"] == "risky"
    assert "disposable" in res["detail"]


def test_smtp_no_mx():
    with mock.patch.object(ev, "_get_mx_hosts", return_value=[]):
        res = ev.verify_email_smtp("foo@bar.com")
    assert res["status"] == "invalid"
    assert "no_mx" in res["detail"]


def test_smtp_valid_mailbox():
    with mock.patch.object(ev, "_get_mx_hosts", return_value=["mx.bar.com"]), \
         mock.patch("smtplib.SMTP", _mock_smtp_factory(250, catch_all_code=550)):
        res = ev.verify_email_smtp("john@bar.com", catch_all_probe=True)
    assert res["status"] == "valid"
    assert res["method"] == "smtp"


def test_smtp_invalid_mailbox_550():
    with mock.patch.object(ev, "_get_mx_hosts", return_value=["mx.bar.com"]), \
         mock.patch("smtplib.SMTP", _mock_smtp_factory(550)):
        res = ev.verify_email_smtp("nope@bar.com", catch_all_probe=False)
    assert res["status"] == "invalid"


def test_smtp_catch_all_detected():
    # Both real + random RCPT return 250 -> catch_all
    with mock.patch.object(ev, "_get_mx_hosts", return_value=["mx.bar.com"]), \
         mock.patch("smtplib.SMTP", _mock_smtp_factory(250, catch_all_code=250)):
        res = ev.verify_email_smtp("john@bar.com", catch_all_probe=True)
    assert res["status"] == "catch_all"


def test_smtp_role_based_demoted_to_risky():
    with mock.patch.object(ev, "_get_mx_hosts", return_value=["mx.bar.com"]), \
         mock.patch("smtplib.SMTP", _mock_smtp_factory(250, catch_all_code=550)):
        res = ev.verify_email_smtp("info@bar.com", catch_all_probe=True)
    assert res["status"] == "risky"
    assert "role_based" in res["detail"]


# ----------------------------- Orchestrator -----------------------------
def test_verify_email_uses_smtp_first_when_valid():
    fake = {"email": "x@y.co", "status": "valid", "method": "smtp", "detail": ""}
    with mock.patch.object(ev, "verify_email_smtp", return_value=fake) as smtp_mock, \
         mock.patch.object(ev, "verify_email_via_providers") as prov_mock:
        res = ev.verify_email("x@y.co")
    assert res["status"] == "valid"
    smtp_mock.assert_called_once()
    prov_mock.assert_not_called()


def test_verify_email_falls_back_to_providers_on_unknown():
    smtp_res = {"email": "x@y.co", "status": "unknown", "method": "smtp", "detail": "timeout"}
    prov_res = {"email": "x@y.co", "status": "invalid", "method": "zerobounce", "detail": "ok"}
    with mock.patch.object(ev, "verify_email_smtp", return_value=smtp_res), \
         mock.patch.object(ev, "verify_email_via_providers", return_value=prov_res):
        res = ev.verify_email("x@y.co")
    assert res["status"] == "invalid"
    assert res["method"] == "zerobounce"
    assert "override_smtp" in res["detail"]


def test_verify_emails_returns_list_no_sleep():
    fake = [{"email": "a@b.co", "status": "valid", "method": "smtp", "detail": ""}]
    with mock.patch.object(ev, "verify_email", side_effect=lambda e, **_: fake[0]):
        out = ev.verify_emails(["a@b.co", "b@b.co"], delay_between=False)
    assert len(out) == 2
    assert all(r["status"] == "valid" for r in out)


# ----------------------------- Provider parsers -----------------------------
def test_provider_skipped_when_no_key(monkeypatch):
    monkeypatch.setattr(ev, "MYEMAILVERIFIER_API_KEY", "")
    monkeypatch.setattr(ev, "ZEROBOUNCE_API_KEY", "")
    monkeypatch.setattr(ev, "HUNTER_API_KEY", "")
    assert ev._verify_via_myemailverifier("a@b.co") is None
    assert ev._verify_via_zerobounce("a@b.co") is None
    assert ev._verify_via_hunter("a@b.co") is None
    assert ev.verify_email_via_providers("a@b.co") is None