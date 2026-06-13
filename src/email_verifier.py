# src/email_verifier.py
"""Email verification — SMTP RCPT + free-tier provider API fallbacks.

Tujuan: naikin akurasi dari "MX-only" jadi alamat-level verification, sebelum
email beneran dipake buat outreach. Sender reputation > volume.

Strategi (zero / low-budget):
    1. SMTP RCPT (gratis, buatan sendiri pake stdlib smtplib + dnspython)
    2. Provider API fallback kalau status risky/unknown:
         - MyEmailVerifier   (100 req/hari gratis)   env: MYEMAILVERIFIER_API_KEY
         - ZeroBounce        (100 req/bulan gratis)  env: ZEROBOUNCE_API_KEY
         - Hunter.io         (50  req/bulan gratis)  env: HUNTER_API_KEY

Pipeline kompatibel: semua fungsi GRACEFUL-FAIL. Network down, library hilang,
rate-limit kena → return "unknown" + reason di details, JANGAN throw.

Status values (string):
    "valid"     → mailbox confirmed exists (SMTP 250 / provider "valid")
    "invalid"   → mailbox confirmed NOT exists (SMTP 550 / provider "invalid")
    "catch_all" → server nerima semua RCPT, gak bisa konfirmasi spesifik
    "risky"     → role-based / disposable / low confidence
    "unknown"   → gagal verify (timeout, blocked, kuota habis, dst)

JANGAN treat "unknown" sebagai bad — banyak server enterprise sengaja block
SMTP probe. Pakai "invalid" doang sebagai signal hapus.
"""
from __future__ import annotations

import os
import random
import re
import smtplib
import socket
import time
from typing import Optional

try:
    import dns.resolver  # type: ignore
    _HAS_DNS = True
except ImportError:
    _HAS_DNS = False

try:
    import httpx  # type: ignore
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


# ============================================================
# Config (env-driven, opsional)
# ============================================================
SMTP_VERIFY_FROM = os.getenv("SMTP_VERIFY_FROM", "verify@idincode-research.local")
SMTP_VERIFY_HELO = os.getenv("SMTP_VERIFY_HELO", "idincode-research.local")
SMTP_VERIFY_TIMEOUT = float(os.getenv("SMTP_VERIFY_TIMEOUT", "10"))
SMTP_VERIFY_MIN_DELAY = float(os.getenv("SMTP_VERIFY_MIN_DELAY", "1.5"))
SMTP_VERIFY_MAX_DELAY = float(os.getenv("SMTP_VERIFY_MAX_DELAY", "3.5"))

MYEMAILVERIFIER_API_KEY = os.getenv("MYEMAILVERIFIER_API_KEY", "")
ZEROBOUNCE_API_KEY = os.getenv("ZEROBOUNCE_API_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")

# Disposable domain list (subset; cukup buat filter most common throwaway)
_DISPOSABLE_DOMAINS = frozenset((
    "mailinator.com", "guerrillamail.com", "10minutemail.com",
    "tempmail.com", "throwawaymail.com", "yopmail.com",
    "trashmail.com", "getnada.com", "fakeinbox.com", "dispostable.com",
    "maildrop.cc", "sharklasers.com", "guerrillamail.info",
    "tempmail.io", "tempr.email", "mintemail.com",
))

_ROLE_LOCALPARTS = frozenset((
    "info", "hello", "contact", "support", "admin", "office",
    "sales", "marketing", "hr", "careers", "team", "help",
    "billing", "accounts", "service", "abuse", "postmaster",
    "webmaster", "noreply", "no-reply",
))

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


# ============================================================
# Helpers
# ============================================================
def _is_valid_format(email: str) -> bool:
    return bool(email) and bool(_EMAIL_RE.match(email.strip()))


def _split(email: str) -> tuple[str, str]:
    local, _, domain = email.strip().lower().partition("@")
    return local, domain


def _is_disposable(domain: str) -> bool:
    return domain.lower() in _DISPOSABLE_DOMAINS


def _is_role(local: str) -> bool:
    return local.lower() in _ROLE_LOCALPARTS


def _get_mx_hosts(domain: str) -> list[str]:
    """Return MX hosts sorted by priority. Fallback ke A record."""
    if not _HAS_DNS:
        return []
    try:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 5.0
        resolver.timeout = 3.0
        answers = resolver.resolve(domain, "MX")
        ranked = sorted(answers, key=lambda r: r.preference)
        return [str(r.exchange).rstrip(".") for r in ranked]
    except Exception:  # noqa: BLE001
        try:
            socket.gethostbyname(domain)
            return [domain]
        except Exception:  # noqa: BLE001
            return []


def _result(
    email: str,
    status: str,
    method: str,
    detail: str = "",
) -> dict:
    return {
        "email": email,
        "status": status,
        "method": method,
        "detail": detail,
    }


# ============================================================
# 1. SMTP RCPT (DIY, gratis)
# ============================================================
def verify_email_smtp(
    email: str,
    *,
    from_addr: Optional[str] = None,
    helo: Optional[str] = None,
    timeout: Optional[float] = None,
    catch_all_probe: bool = True,
) -> dict:
    """SMTP RCPT probe — ngetuk server tujuan tanpa ngirim email beneran.

    Returns dict {email, status, method, detail}.
    method = "smtp"
    """
    if not _is_valid_format(email):
        return _result(email, "invalid", "smtp", "bad_format")

    local, domain = _split(email)

    if _is_disposable(domain):
        return _result(email, "risky", "smtp", "disposable_domain")

    mx_hosts = _get_mx_hosts(domain)
    if not mx_hosts:
        return _result(email, "invalid", "smtp", "no_mx_or_a_record")

    from_addr = from_addr or SMTP_VERIFY_FROM
    helo = helo or SMTP_VERIFY_HELO
    timeout = timeout if timeout is not None else SMTP_VERIFY_TIMEOUT

    last_err = ""
    for mx in mx_hosts:
        try:
            with smtplib.SMTP(mx, 25, timeout=timeout) as srv:
                srv.ehlo_or_helo_if_needed()
                try:
                    srv.helo(helo)
                except smtplib.SMTPException:
                    pass
                try:
                    srv.mail(from_addr)
                except smtplib.SMTPException as e:
                    last_err = f"mail_from_rejected:{e}"
                    continue

                code, _msg = srv.rcpt(email)
                # 250 / 251 = accepted
                if code in (250, 251):
                    status = "valid"
                    detail = f"mx={mx},code={code}"

                    # Catch-all probe: server yang nerima semua RCPT
                    # akan juga nerima alamat random. Kalau iya → catch_all.
                    if catch_all_probe:
                        rand_local = f"idincode-probe-{int(time.time()*1000)%99999}"
                        rand_email = f"{rand_local}@{domain}"
                        try:
                            rc, _ = srv.rcpt(rand_email)
                            if rc in (250, 251):
                                status = "catch_all"
                                detail = f"{detail},catch_all=true"
                        except smtplib.SMTPException:
                            pass

                    # Tag role-based as risky even kalau accepted
                    if status == "valid" and _is_role(local):
                        status = "risky"
                        detail += ",role_based"
                    return _result(email, status, "smtp", detail)

                # 550/551/553 = mailbox unavailable
                if code in (550, 551, 553, 554):
                    return _result(email, "invalid", "smtp",
                                   f"mx={mx},code={code}")

                # 4xx greylist / tempfail / 252 = "cannot vrfy but try"
                last_err = f"mx={mx},code={code}"
        except (smtplib.SMTPException, socket.timeout, ConnectionError, OSError) as e:
            last_err = f"mx={mx},err={type(e).__name__}:{e}"
            continue

    return _result(email, "unknown", "smtp", last_err or "all_mx_failed")


# ============================================================
# 2. Provider API fallbacks (free-tier)
# ============================================================
def _verify_via_myemailverifier(email: str, *, timeout: float = 10.0) -> Optional[dict]:
    """MyEmailVerifier API — 100 req/hari gratis.
    Docs: https://www.myemailverifier.com/api-documentation
    """
    if not (MYEMAILVERIFIER_API_KEY and _HAS_HTTPX):
        return None
    url = f"https://client.myemailverifier.com/verifier/validate_single/{email}/{MYEMAILVERIFIER_API_KEY}"
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url)
            r.raise_for_status()
            data = r.json()
        status = (data.get("Status") or "").lower()
        sub = (data.get("Diagnosis") or "").lower()
        mapping = {
            "valid": "valid",
            "invalid": "invalid",
            "catch-all": "catch_all",
            "catchall": "catch_all",
            "unknown": "unknown",
        }
        mapped = mapping.get(status, "unknown")
        if mapped == "valid" and "role" in sub:
            mapped = "risky"
        return _result(email, mapped, "myemailverifier",
                       f"status={status},diag={sub}")
    except Exception as e:  # noqa: BLE001
        return _result(email, "unknown", "myemailverifier",
                       f"err={type(e).__name__}:{e}")


def _verify_via_zerobounce(email: str, *, timeout: float = 10.0) -> Optional[dict]:
    """ZeroBounce API — 100 req/bulan gratis.
    Docs: https://www.zerobounce.net/docs/email-validation-api-quickstart
    """
    if not (ZEROBOUNCE_API_KEY and _HAS_HTTPX):
        return None
    url = "https://api.zerobounce.net/v2/validate"
    params = {"api_key": ZEROBOUNCE_API_KEY, "email": email, "ip_address": ""}
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        status = (data.get("status") or "").lower()
        sub = (data.get("sub_status") or "").lower()
        mapping = {
            "valid": "valid",
            "invalid": "invalid",
            "catch-all": "catch_all",
            "do_not_mail": "risky",
            "spamtrap": "risky",
            "abuse": "risky",
            "unknown": "unknown",
        }
        mapped = mapping.get(status, "unknown")
        if mapped == "valid" and "role" in sub:
            mapped = "risky"
        return _result(email, mapped, "zerobounce",
                       f"status={status},sub={sub}")
    except Exception as e:  # noqa: BLE001
        return _result(email, "unknown", "zerobounce",
                       f"err={type(e).__name__}:{e}")


def _verify_via_hunter(email: str, *, timeout: float = 10.0) -> Optional[dict]:
    """Hunter.io email-verifier — 50 req/bulan gratis.
    Docs: https://hunter.io/api-documentation/v2#email-verifier
    """
    if not (HUNTER_API_KEY and _HAS_HTTPX):
        return None
    url = "https://api.hunter.io/v2/email-verifier"
    params = {"email": email, "api_key": HUNTER_API_KEY}
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = (r.json() or {}).get("data", {}) or {}
        status = (data.get("status") or "").lower()
        mapping = {
            "valid": "valid",
            "invalid": "invalid",
            "accept_all": "catch_all",
            "webmail": "risky",
            "disposable": "risky",
            "unknown": "unknown",
        }
        mapped = mapping.get(status, "unknown")
        return _result(email, mapped, "hunter",
                       f"status={status},score={data.get('score')}")
    except Exception as e:  # noqa: BLE001
        return _result(email, "unknown", "hunter",
                       f"err={type(e).__name__}:{e}")


_PROVIDER_FALLBACKS = (
    _verify_via_myemailverifier,
    _verify_via_zerobounce,
    _verify_via_hunter,
)


def verify_email_via_providers(email: str) -> Optional[dict]:
    """Coba semua provider yang punya API key. Pertama yang return non-unknown menang."""
    last: Optional[dict] = None
    for fn in _PROVIDER_FALLBACKS:
        res = fn(email)
        if res is None:
            continue
        last = res
        if res.get("status") in ("valid", "invalid", "catch_all", "risky"):
            return res
    return last


# ============================================================
# 3. Top-level orchestrator
# ============================================================
def verify_email(
    email: str,
    *,
    use_smtp: bool = True,
    use_providers: bool = True,
    smtp_first: bool = True,
) -> dict:
    """Verify satu email. Coba SMTP dulu (gratis), fallback ke provider API.

    Aturan keputusan:
        - Status "valid" / "invalid" dari sumber manapun → langsung pakai.
        - "catch_all" / "risky" dari SMTP → coba provider buat second opinion.
        - Provider hanya dipanggil kalau API key di-set.
    """
    if not _is_valid_format(email):
        return _result(email, "invalid", "format", "bad_format")

    primary: dict
    if smtp_first and use_smtp:
        primary = verify_email_smtp(email)
    elif use_providers:
        provider = verify_email_via_providers(email)
        primary = provider or _result(email, "unknown", "none", "no_provider_configured")
    else:
        primary = verify_email_smtp(email) if use_smtp else _result(
            email, "unknown", "none", "all_methods_disabled"
        )

    # Confident -> done.
    if primary["status"] in ("valid", "invalid"):
        return primary

    # Risky / catch_all / unknown → minta second opinion ke provider.
    if use_providers:
        second = verify_email_via_providers(email)
        if second and second["status"] in ("valid", "invalid"):
            second["detail"] = f"override_smtp({primary['status']});{second['detail']}"
            return second
        # If both unknown, prefer the more informative one (smtp catch_all > unknown).
        if second and primary["status"] == "unknown" and second["status"] != "unknown":
            return second

    return primary


def verify_emails(
    emails: list[str],
    *,
    use_smtp: bool = True,
    use_providers: bool = True,
    delay_between: bool = True,
) -> list[dict]:
    """Verify multiple emails dengan jitter delay biar gak kena rate-limit IP-level."""
    out: list[dict] = []
    n = len(emails)
    for i, em in enumerate(emails):
        out.append(verify_email(
            em,
            use_smtp=use_smtp,
            use_providers=use_providers,
        ))
        if delay_between and use_smtp and i < n - 1:
            time.sleep(random.uniform(
                SMTP_VERIFY_MIN_DELAY, SMTP_VERIFY_MAX_DELAY
            ))
    return out


# ============================================================
# 4. Roll-up helpers (untuk export.py / qualifier.py)
# ============================================================
_STATUS_RANK = {
    "valid": 4,
    "catch_all": 3,
    "risky": 2,
    "unknown": 1,
    "invalid": 0,
}


def best_status(statuses: list[str]) -> str:
    """Ambil status terbaik dari list (untuk roll-up per domain)."""
    if not statuses:
        return "unknown"
    return max(statuses, key=lambda s: _STATUS_RANK.get(s, -1))


def is_deliverable(status: str) -> bool:
    """Aman buat outreach? valid + catch_all = ya (catch_all = abu-abu)."""
    return status in ("valid", "catch_all")


__all__ = [
    "verify_email",
    "verify_email_smtp",
    "verify_email_via_providers",
    "verify_emails",
    "best_status",
    "is_deliverable",
]