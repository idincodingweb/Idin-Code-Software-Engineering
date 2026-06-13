# src/crm_webhooks.py
"""CRM Webhook dispatcher.

Roadmap v3.4: push qualified leads ke CRM lewat incoming webhook.
Support: HubSpot, Pipedrive, Salesforce, Airtable, Zoho + generic.

DESAIN (penting):
- Config via ENV (backward-compatible, gak nyentuh YAML / file lama).
- Tiap provider OFF by default. Aktif HANYA kalau URL-nya di-set di env.
- Kirim payload JSON ter-normalisasi per lead. Endpoint yang dimaksud =
  *incoming webhook* (native automation / Zapier / Make / Airtable Web API),
  bukan SDK. Ini bikin tool tetep standalone & legal (cuma HTTP POST).
- Fail-safe: error per-lead/per-provider gak bikin pipeline mati. Selalu
  return summary dict buat reporting.
- Dukung dry-run: cetak payload, gak ngirim apa-apa (buat lo verifikasi
  sebelum blast beneran).

ENV yang dibaca:
    CRM_HUBSPOT_WEBHOOK_URL
    CRM_PIPEDRIVE_WEBHOOK_URL
    CRM_SALESFORCE_WEBHOOK_URL
    CRM_AIRTABLE_WEBHOOK_URL
    CRM_ZOHO_WEBHOOK_URL
    CRM_GENERIC_WEBHOOK_URL        (boleh comma-separated buat banyak endpoint)
    CRM_WEBHOOK_AUTH_HEADER        (opsional, dikirim sbg header "Authorization")
    CRM_WEBHOOK_TIMEOUT            (opsional, detik, default 15)
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

import httpx

# provider -> env var URL
_PROVIDER_ENV: dict[str, str] = {
    "hubspot": "CRM_HUBSPOT_WEBHOOK_URL",
    "pipedrive": "CRM_PIPEDRIVE_WEBHOOK_URL",
    "salesforce": "CRM_SALESFORCE_WEBHOOK_URL",
    "airtable": "CRM_AIRTABLE_WEBHOOK_URL",
    "zoho": "CRM_ZOHO_WEBHOOK_URL",
    "generic": "CRM_GENERIC_WEBHOOK_URL",
}

_DEFAULT_TIMEOUT = 15.0


# ============================================================
# Config
# ============================================================
def load_crm_targets(env: Optional[dict[str, str]] = None) -> list[tuple[str, str]]:
    """Baca env, return list (provider, url). Generic boleh multi (comma-sep)."""
    env = env if env is not None else dict(os.environ)
    targets: list[tuple[str, str]] = []
    for provider, var in _PROVIDER_ENV.items():
        raw = (env.get(var) or "").strip()
        if not raw:
            continue
        for url in raw.split(","):
            url = url.strip()
            if url:
                targets.append((provider, url))
    return targets


def crm_configured(env: Optional[dict[str, str]] = None) -> bool:
    return bool(load_crm_targets(env))


# ============================================================
# Payload formatting
# ============================================================
def _base_record(lead: Any) -> dict[str, Any]:
    """Normalisasi 1 lead jadi flat dict (provider-agnostic)."""
    emails = list(getattr(lead, "emails_found", []) or [])
    return {
        "domain": getattr(lead, "domain", ""),
        "primary_email": emails[0] if emails else "",
        "emails": ", ".join(emails),
        "location": getattr(lead, "location", "") or "",
        "niche": getattr(lead, "niche", "") or "",
        "category": getattr(lead, "category", "") or "",
        "gold_score": round(float(getattr(lead, "score", 0.0) or 0.0), 4),
        "quality_score": int(getattr(lead, "quality_score", 0) or 0),
        "platform": getattr(lead, "platform", "") or "",
        "revenue_tier": getattr(lead, "revenue_tier", "") or "",
        "bi_score": int(getattr(lead, "bi_score", 0) or 0),
        "employee_range": getattr(lead, "employee_range", "") or "",
        "founded_year": getattr(lead, "founded_year", None),
        "mx_valid": getattr(lead, "mx_valid", None),
        "running_meta_ads": getattr(lead, "running_meta_ads", None),
        "gold_reasons": getattr(lead, "gold_reasons", "") or "",
        "outreach_angle": getattr(lead, "outreach_angle", "") or "",
        "bi_summary": getattr(lead, "bi_summary", "") or "",
    }


def format_payload(provider: str, lead: Any) -> dict[str, Any]:
    """Bentuk payload per provider.

    - airtable : {"records": [{"fields": {...}}]}  (Airtable Web API format)
    - lainnya  : flat record + meta {"source": "...", "provider": "..."}
    """
    record = _base_record(lead)
    if provider == "airtable":
        return {"records": [{"fields": record}]}
    return {
        "source": "idincode-researche",
        "provider": provider,
        "lead": record,
    }


# ============================================================
# Dispatch
# ============================================================
async def _post_one(
    client: httpx.AsyncClient,
    provider: str,
    url: str,
    lead: Any,
    *,
    headers: dict[str, str],
    max_retries: int = 2,
) -> bool:
    payload = format_payload(provider, lead)
    last_err: Optional[str] = None
    for attempt in range(max_retries + 1):
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if 200 <= resp.status_code < 300:
                return True
            last_err = f"HTTP {resp.status_code}: {resp.text[:160]}"
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
                continue
            break
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
                continue
            break
    print(f"[crm] {provider} push fail for "
          f"{getattr(lead, 'domain', '?')}: {last_err}")
    return False


async def push_leads_to_crm(
    leads: list[Any],
    *,
    min_score: float = 0.70,
    limit: int = 0,
    dry_run: bool = False,
    max_concurrent: int = 4,
    env: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Push leads (yang score >= min_score) ke semua CRM target yang ke-config.

    Args:
        min_score: filter gold_score minimum (0..1).
        limit: max lead yang dikirim (0 = semua yang lolos filter).
        dry_run: kalau True, cetak payload doang, gak POST.

    Return summary dict: configured providers, selected count, sent, failed.
    """
    targets = load_crm_targets(env)
    selected = [l for l in leads if float(getattr(l, "score", 0.0) or 0.0) >= min_score]
    selected.sort(key=lambda l: float(getattr(l, "score", 0.0) or 0.0), reverse=True)
    if limit and limit > 0:
        selected = selected[:limit]

    summary: dict[str, Any] = {
        "providers": [p for p, _ in targets],
        "endpoints": len(targets),
        "selected": len(selected),
        "sent": 0,
        "failed": 0,
        "dry_run": dry_run,
        "skipped_reason": None,
    }

    if not targets:
        summary["skipped_reason"] = "no CRM webhook configured (set CRM_*_WEBHOOK_URL)"
        print("[crm] skip: " + summary["skipped_reason"])
        return summary

    if not selected:
        summary["skipped_reason"] = f"no lead with gold_score >= {min_score}"
        print("[crm] skip: " + summary["skipped_reason"])
        return summary

    if dry_run:
        print(f"[crm] DRY-RUN: would push {len(selected)} lead(s) to "
              f"{len(targets)} endpoint(s): {[p for p, _ in targets]}")
        for provider, _ in targets:
            for lead in selected[:3]:
                print(f"[crm]   {provider} <- {format_payload(provider, lead)}")
        summary["sent"] = 0
        return summary

    headers = {"Content-Type": "application/json"}
    auth = (env or os.environ).get("CRM_WEBHOOK_AUTH_HEADER", "").strip()
    if auth:
        headers["Authorization"] = auth

    try:
        timeout = float((env or os.environ).get("CRM_WEBHOOK_TIMEOUT", "") or _DEFAULT_TIMEOUT)
    except ValueError:
        timeout = _DEFAULT_TIMEOUT

    sem = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async def _bounded(provider: str, url: str, lead: Any) -> bool:
            async with sem:
                return await _post_one(client, provider, url, lead, headers=headers)

        jobs = [
            _bounded(provider, url, lead)
            for provider, url in targets
            for lead in selected
        ]
        results = await asyncio.gather(*jobs)

    summary["sent"] = sum(1 for r in results if r)
    summary["failed"] = sum(1 for r in results if not r)
    print(f"[crm] done: sent={summary['sent']} failed={summary['failed']} "
          f"(providers={summary['providers']}, leads={len(selected)})")
    return summary
