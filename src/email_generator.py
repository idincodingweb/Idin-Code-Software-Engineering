"""AI Personalized Email Generator.

Generate cold email (subject, body, CTA) per lead/buyer via kie.ai (Claude).

Re-use konfigurasi yang sama dengan analyst.py/buyer_analyst.py supaya
konsisten dengan AI macro yang udah lo set.

Public API:
    generate_emails_for_leads(qualified_leads, *, batch_size, max_retries) -> dict
    generate_emails_for_buyers(buyer_leads, *, batch_size, max_retries)    -> dict

Output dict:
    {
        "<domain>":            # untuk leads pipeline
        OR "<domain>|<email>": # untuk buyers pipeline (1 person)
        {
            "subject": "...",
            "body":    "...",   # plain text, multi-paragraph
            "cta":     "..."
        }
    }

Fallback: kalau IDINCODE_API kosong atau API gagal -> template fallback
yang TETAP usable (gak crash pipeline).
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from src.analyst import _extract_text_from_response
from src.config import (
    IDINCODE_API,
    KIE_AI_BASE_URL,
    KIE_AI_MESSAGES_PATH,
    KIE_AI_MODEL,
    KIE_AI_THINKING,
)


# ============================================================
# Sender identity (operator email used in signature + reply-to hint).
# Centralized so semua prompt + fallback template konsisten.
# ============================================================
SENDER_NAME = "Idin Iskandar"
SENDER_EMAIL = "idiniskandar.tech@gmail.com"
SIGNATURE = f"— {SENDER_NAME}\n{SENDER_EMAIL}"
# Tagline final yang WAJIB muncul di akhir setiap body email:
# soft feedback ask + janji kirim sample. Bahasa Inggris (target global).
FEEDBACK_LINE = (
    "If you're open to giving honest feedback, I'll happily send you "
    "a sample of my software's output."
)


# ============================================================
# Prompts
# ============================================================
def _system_for_leads() -> str:
    return (
        "You are an elite B2B cold email copywriter helping the operator "
        f"({SENDER_NAME}, {SENDER_EMAIL}) write to CLINIC / BUSINESS "
        "owners. The software is NEW and unbranded. The operator is "
        "NOT pitching a service and NOT selling anything. The ONLY "
        "goal of the email is to ask the recipient for honest feedback "
        "on a small audit of their website. In exchange the operator "
        "offers to send a free sample of the software's output.\n\n"
        "For each lead, produce a cold email with:\n"
        "  - subject: <55 chars, plain English, pattern-interrupt, NO "
        "clickbait, NO emoji, NO ALL CAPS.\n"
        "  - body: 3-5 short paragraphs, conversational, plain text. "
        "Mention ONE specific issue (slow LCP, missing pixel, no GA4, "
        "etc) from the data given. Frame as 'I noticed X, would value "
        "your honest take'. NOT a sales pitch. Avoid buzzwords like "
        "'leverage' / 'synergy' / 'unlock'. The SECOND-TO-LAST "
        f'paragraph MUST be exactly this line (verbatim): "{FEEDBACK_LINE}". '
        f'End with this signature on its own paragraph: "{SIGNATURE}".\n'
        "  - cta: 1 sentence soft feedback ask (e.g. 'Worth a quick "
        "reply with your honest take?').\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON. NO markdown fences.\n"
        '2. Format: {"results": {"<domain>": {"subject": "...", "body": "...", "cta": "..."}}}\n'
        "3. Body uses \\n\\n for paragraph breaks.\n"
        "4. NEVER invent data not present in the input.\n"
        "5. NEVER use hard-sell language. This is feedback collection."
    )


def _system_for_buyers() -> str:
    return (
        "You are an elite B2B cold email copywriter. The operator "
        f"({SENDER_NAME}, {SENDER_EMAIL}) built a self-hosted data "
        "pipeline that scrapes and scores business websites for "
        "marketing gaps. The software is NEW and unbranded. The "
        "operator is NOT hard-selling. The ONLY goal of the email is "
        "to ask the agency decision maker for honest feedback. In "
        "exchange the operator offers a free sample of the software's "
        "output.\n\n"
        "Target: a decision maker (CEO/Founder/Owner/Partner) at an "
        "agency. Write a cold email with:\n"
        "  - subject: <55 chars, specific to their niche, plain "
        "English, pattern-interrupt, NO emoji, NO ALL CAPS.\n"
        "  - body: 3-5 short paragraphs. Address by FIRST name. "
        "Reference their probable service line. Plain text. No emoji. "
        "Frame as 'I built this, would value your honest opinion'. "
        "The SECOND-TO-LAST paragraph MUST be exactly this line "
        f'(verbatim): "{FEEDBACK_LINE}". '
        f'End with this signature on its own paragraph: "{SIGNATURE}".\n'
        "  - cta: 1 sentence soft feedback ask (e.g. 'Worth a quick "
        "reply with your honest take?').\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON. NO markdown fences.\n"
        '2. Format: {"results": {"<domain>|<email>": {"subject": "...", "body": "...", "cta": "..."}}}\n'
        "3. Body uses \\n\\n for paragraph breaks.\n"
        "4. NEVER invent data not present in the input.\n"
        "5. NEVER use hard-sell language. This is feedback collection."
    )


def _user_prompt_leads(leads: list[Any]) -> str:
    lines = [
        "Generate cold email for each lead. JSON only.",
        "",
        "Leads:",
    ]
    for l in leads:
        issues = []
        if getattr(l, "pagespeed_score", None) is not None and l.pagespeed_score < 60:
            issues.append(f"slow mobile speed (pagespeed={l.pagespeed_score})")
        if getattr(l, "lcp_ms", None) is not None and l.lcp_ms > 3500:
            issues.append(f"LCP {l.lcp_ms}ms (>3.5s)")
        if not getattr(l, "meta_pixel_in_html", False):
            issues.append("no Meta pixel in HTML")
        if not getattr(l, "ga4_in_html", False):
            issues.append("no GA4 tracking")
        if not getattr(l, "google_ads_in_html", False):
            issues.append("no Google Ads remarketing")
        issue_str = "; ".join(issues) or "general optimization opportunities"
        lines.append(
            f"- domain={l.domain} | niche={l.niche} | "
            f"location={l.location or 'unknown'} | score={l.score} | "
            f"issues={issue_str}"
        )
    lines.append("")
    lines.append("Remember: JSON only, no markdown.")
    return "\n".join(lines)


def _user_prompt_buyers(rows: list[dict]) -> str:
    """rows: list[{'key','domain','agency_name','niche_keyword','country','first_name','title'}]"""
    lines = [
        "Generate cold email for each agency decision maker. JSON only.",
        "",
        "Persons:",
    ]
    for r in rows:
        lines.append(
            f"- key={r['key']} | first_name={r['first_name']} | "
            f"title={r['title']} | agency={r['agency_name']} | "
            f"domain={r['domain']} | niche={r['niche_keyword']} | "
            f"country={r['country']}"
        )
    lines.append("")
    lines.append("Remember: JSON only, no markdown.")
    return "\n".join(lines)


# ============================================================
# Core call
# ============================================================
async def _call_kie(
    system: str, user: str, *, max_retries: int = 2
) -> dict[str, Any]:
    payload = {
        "model": KIE_AI_MODEL,
        "max_tokens": 4096,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "thinkingFlag": KIE_AI_THINKING,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {IDINCODE_API}",
        "Content-Type": "application/json",
    }
    url = f"{KIE_AI_BASE_URL.rstrip('/')}{KIE_AI_MESSAGES_PATH}"

    last: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                text = _extract_text_from_response(resp.json())
                if not text:
                    raise ValueError("empty AI text")
                return _parse(text)
            if resp.status_code in (429, 500, 502, 503, 504):
                last = RuntimeError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
            raise RuntimeError(
                f"HTTP {resp.status_code}: {resp.text[:200]}"
            )
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < max_retries:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            raise
    if last:
        raise last
    return {}


def _parse(text: str) -> dict[str, Any]:
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.MULTILINE)
    # extract first {...} block
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in AI response")
    data = json.loads(m.group(0))
    return data.get("results", {}) if isinstance(data, dict) else {}


# ============================================================
# Public: LEADS
# ============================================================
async def generate_emails_for_leads(
    leads: list[Any],
    *,
    batch_size: int = 8,
    max_retries: int = 2,
) -> dict[str, dict[str, str]]:
    """Return {domain: {subject, body, cta}}."""
    out: dict[str, dict[str, str]] = {}
    if not leads:
        return out

    if not IDINCODE_API:
        print("[email-gen] IDINCODE_API kosong, pakai fallback template")
        for l in leads:
            out[l.domain] = _fallback_lead(l)
        return out

    print(f"[email-gen] Generate cold email untuk {len(leads)} leads...")
    for i in range(0, len(leads), batch_size):
        chunk = leads[i:i + batch_size]
        try:
            results = await _call_kie(
                _system_for_leads(),
                _user_prompt_leads(chunk),
                max_retries=max_retries,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[email-gen] WARN batch {i}: {type(e).__name__}: {e}, fallback")
            for l in chunk:
                out[l.domain] = _fallback_lead(l)
            continue
        for l in chunk:
            data = results.get(l.domain)
            if isinstance(data, dict) and data.get("body"):
                out[l.domain] = {
                    "subject": str(data.get("subject", "")).strip()
                    or _fallback_lead(l)["subject"],
                    "body": str(data.get("body", "")).strip(),
                    "cta": str(data.get("cta", "")).strip()
                    or _fallback_lead(l)["cta"],
                }
            else:
                out[l.domain] = _fallback_lead(l)
    return out


# ============================================================
# Public: BUYERS
# ============================================================
async def generate_emails_for_buyers(
    buyer_leads: list[Any],
    *,
    batch_size: int = 8,
    max_retries: int = 2,
) -> dict[str, dict[str, str]]:
    """Return {"<domain>|<email>": {subject, body, cta}}.

    buyer_leads: list[BuyerLead] (from src.buyer_finder)
    """
    out: dict[str, dict[str, str]] = {}
    rows: list[dict] = []
    for l in buyer_leads:
        for p in l.persons:
            if not p.email:
                continue
            first = p.name.split()[0] if p.name else ""
            rows.append({
                "key": f"{l.agency_domain}|{p.email.lower()}",
                "domain": l.agency_domain,
                "agency_name": l.agency_name,
                "niche_keyword": l.niche_keyword,
                "country": l.country,
                "first_name": first,
                "title": p.title,
                "_person": p,
                "_lead": l,
            })
    if not rows:
        return out

    if not IDINCODE_API:
        print("[email-gen] IDINCODE_API kosong, pakai fallback template")
        for r in rows:
            out[r["key"]] = _fallback_buyer(r)
        return out

    print(f"[email-gen] Generate cold email untuk {len(rows)} buyer persons...")
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        try:
            # strip _person/_lead before sending to AI
            prompt_chunk = [
                {k: v for k, v in r.items() if not k.startswith("_")}
                for r in chunk
            ]
            results = await _call_kie(
                _system_for_buyers(),
                _user_prompt_buyers(prompt_chunk),
                max_retries=max_retries,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[email-gen] WARN batch {i}: {type(e).__name__}: {e}, fallback")
            for r in chunk:
                out[r["key"]] = _fallback_buyer(r)
            continue
        for r in chunk:
            data = results.get(r["key"])
            if isinstance(data, dict) and data.get("body"):
                out[r["key"]] = {
                    "subject": str(data.get("subject", "")).strip()
                    or _fallback_buyer(r)["subject"],
                    "body": str(data.get("body", "")).strip(),
                    "cta": str(data.get("cta", "")).strip()
                    or _fallback_buyer(r)["cta"],
                }
            else:
                out[r["key"]] = _fallback_buyer(r)
    return out


# ============================================================
# Fallbacks (template — selalu jalan)
# ============================================================
def _fallback_lead(l: Any) -> dict[str, str]:
    issue = "your site loading speed"
    if getattr(l, "pagespeed_score", None) is not None and l.pagespeed_score < 60:
        issue = f"your mobile PageSpeed score ({l.pagespeed_score}/100)"
    elif not getattr(l, "meta_pixel_in_html", False):
        issue = "the missing Meta pixel on your site"
    elif not getattr(l, "ga4_in_html", False):
        issue = "the missing GA4 tracking on your site"

    subject = f"Quick audit note on {l.domain} — feedback?"
    body = (
        f"Hi team,\n\n"
        f"I ran a small automated audit on {l.domain} and noticed "
        f"{issue}. In the {l.niche or 'your'} space this kind of "
        f"thing usually costs bookings — the visitor bounces before "
        f"the page even finishes loading.\n\n"
        f"I'm not pitching anything. I built a small software that "
        f"checks public signals (speed, tracking pixels, GA4, etc) "
        f"and I'd love your honest take on whether the finding is "
        f"useful or off-base.\n\n"
        f"{FEEDBACK_LINE}\n\n"
        f"{SIGNATURE}"
    )
    cta = "Worth a quick reply with your honest take?"
    return {"subject": subject, "body": body, "cta": cta}


def _fallback_buyer(r: dict) -> dict[str, str]:
    first = r["first_name"] or "there"
    niche = r["niche_keyword"]
    subject = f"Built a {niche} lead scorer — feedback?"
    body = (
        f"Hi {first},\n\n"
        f"Saw you run {r['agency_name']} in the {niche} space. I "
        f"built a small data pipeline that scrapes and scores "
        f"business websites in that exact niche for marketing gaps "
        f"(weak pixels, slow sites, missing tracking).\n\n"
        f"The software is still new and unbranded — I'm not pitching "
        f"a contract, just trying to validate whether this kind of "
        f"pre-scored list is actually useful for an agency like "
        f"yours.\n\n"
        f"{FEEDBACK_LINE}\n\n"
        f"{SIGNATURE}"
    )
    cta = "Worth a quick reply with your honest take?"
    return {"subject": subject, "body": body, "cta": cta}


# ============================================================
# AGENCY PITCH MODE (v3.3+)
#
# Beda sama _system_for_buyers():
#   - buyers      = jual leads ke agency, fokus subject niche-specific.
#   - agency_pitch= jual sample lead pack (PDF/CSV attachment) ke agency luar
#                   (US/UK/AU/EU), tone = friendly outsider asking feedback,
#                   bukan hard sell. Bunyi natural + bahasa Inggris bersih.
#
# Input row = sama dgn buyers (dict dengan key/agency_name/first_name/title/
#             niche_keyword/country/domain) + optional sample_summary dict:
#             {"niche": "...", "count": N, "csv_file": "...", "pdf_file": "..."}
# ============================================================
def _system_for_agency_pitch() -> str:
    return (
        "You are an elite B2B cold email copywriter helping the operator "
        "(Idin Iskandar) reach out to SMALL/MID DIGITAL MARKETING AGENCIES "
        "located OUTSIDE Indonesia (mainly US, UK, AU, EU). The operator "
        "runs a self-built data pipeline that scores business websites "
        "(clinics, med spas, dental, plastic surgery, etc) for marketing "
        "gaps and produces a 'sample lead pack' (CSV + PDF) attached to "
        "the email.\n\n"
        "Goal of the email: get the agency owner to OPEN the sample pack "
        "and reply with feedback. NOT a hard sell. NOT a contract pitch. "
        "Frame as: 'I built a tool, would value your honest opinion on "
        "this sample'.\n\n"
        "For each recipient produce:\n"
        "  - subject: <55 chars, plain English, NO emoji, NO clickbait, "
        "NO ALL CAPS. Pattern interrupt OK (e.g. 'Sample lead pack for "
        "{niche} — feedback?'). Avoid generic 'Quick question'.\n"
        "  - body: 4-6 SHORT paragraphs, plain text, real-human tone. "
        "First paragraph: 1-line context (who you are, why you're "
        "writing). Second: what the attached sample contains and how "
        "it was generated (public signals only). Third: what you'd "
        "love feedback on (pricing, depth, niche fit). Fourth: a soft "
        "offer (more samples or a niche-on-request). Plain text, no "
        "buzzwords ('synergy', 'unlock', 'leverage', 'game-changer'). "
        "Address by FIRST name when available. The SECOND-TO-LAST "
        f'paragraph MUST be exactly this line (verbatim): "{FEEDBACK_LINE}". '
        f'End with this signature on its own paragraph: "{SIGNATURE}".\n'
        "  - cta: 1 sentence soft feedback ask (e.g. 'Worth a quick "
        "reply with your honest take?').\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON. NO markdown fences.\n"
        '2. Format: {"results": {"<key>": {"subject": "...", "body": "...", "cta": "..."}}}\n'
        "3. Body uses \\n\\n for paragraph breaks.\n"
        "4. NEVER invent stats or claims not present in the input.\n"
        "5. Mention 'attached sample pack' once — don't repeat.\n"
        "6. NEVER use hard-sell language. This is feedback collection."
    )


def _user_prompt_agency_pitch(
    rows: list[dict], sample: dict | None
) -> str:
    s = sample or {}
    lines = [
        "Generate cold pitch emails for each agency. Plain English. JSON only.",
        "",
        f"Sample pack context:",
        f"  niche      = {s.get('niche', 'mixed')}",
        f"  sample_size= {s.get('count', 'a small batch of')}",
        f"  format     = CSV + 1-page PDF showcase (attached to email)",
        f"  source     = public website signals (PageSpeed, missing pixels, "
        f"missing analytics, slow LCP). No scraping of private data.",
        "",
        "Recipients:",
    ]
    for r in rows:
        lines.append(
            f"- key={r['key']} | first_name={r['first_name']} | "
            f"title={r['title']} | agency={r['agency_name']} | "
            f"domain={r['domain']} | niche={r['niche_keyword']} | "
            f"country={r['country']}"
        )
    lines.append("")
    lines.append("Remember: JSON only, no markdown.")
    return "\n".join(lines)


async def generate_emails_for_agency_pitch(
    buyer_leads: list[Any],
    *,
    sample_summary: dict | None = None,
    batch_size: int = 8,
    max_retries: int = 2,
) -> dict[str, dict[str, str]]:
    """Return {"<domain>|<email>": {subject, body, cta}}.

    buyer_leads: list with .agency_domain, .agency_name, .niche_keyword,
                 .country, .persons[].name/.title/.email (same shape as
                 generate_emails_for_buyers).
    sample_summary: optional dict {niche, count, csv_file, pdf_file}
                    used as context only (NOT echoed verbatim into AI).
    """
    out: dict[str, dict[str, str]] = {}
    rows: list[dict] = []
    for l in buyer_leads:
        for p in l.persons:
            if not p.email:
                continue
            first = p.name.split()[0] if p.name else ""
            rows.append({
                "key": f"{l.agency_domain}|{p.email.lower()}",
                "domain": l.agency_domain,
                "agency_name": l.agency_name,
                "niche_keyword": l.niche_keyword,
                "country": l.country,
                "first_name": first,
                "title": p.title,
                "_person": p,
                "_lead": l,
            })
    if not rows:
        return out

    if not IDINCODE_API:
        print("[email-gen] IDINCODE_API kosong, pakai fallback agency-pitch template")
        for r in rows:
            out[r["key"]] = _fallback_agency_pitch(r, sample_summary)
        return out

    print(f"[email-gen] Generate AGENCY PITCH untuk {len(rows)} persons "
          f"(sample niche={sample_summary.get('niche') if sample_summary else 'n/a'})")
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        try:
            prompt_chunk = [
                {k: v for k, v in r.items() if not k.startswith("_")}
                for r in chunk
            ]
            results = await _call_kie(
                _system_for_agency_pitch(),
                _user_prompt_agency_pitch(prompt_chunk, sample_summary),
                max_retries=max_retries,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[email-gen] WARN agency-pitch batch {i}: "
                  f"{type(e).__name__}: {e}, fallback")
            for r in chunk:
                out[r["key"]] = _fallback_agency_pitch(r, sample_summary)
            continue
        for r in chunk:
            data = results.get(r["key"])
            if isinstance(data, dict) and data.get("body"):
                out[r["key"]] = {
                    "subject": str(data.get("subject", "")).strip()
                    or _fallback_agency_pitch(r, sample_summary)["subject"],
                    "body": str(data.get("body", "")).strip(),
                    "cta": str(data.get("cta", "")).strip()
                    or _fallback_agency_pitch(r, sample_summary)["cta"],
                }
            else:
                out[r["key"]] = _fallback_agency_pitch(r, sample_summary)
    return out


def _fallback_agency_pitch(r: dict, sample: dict | None) -> dict[str, str]:
    s = sample or {}
    first = r["first_name"] or "there"
    niche = (s.get("niche") or r["niche_keyword"] or "your niche")
    count = s.get("count") or "a small batch of"
    subject = f"Sample lead pack for {niche} — feedback?"
    body = (
        f"Hi {first},\n\n"
        f"I run a small data pipeline that scores business websites for "
        f"marketing gaps — slow mobile speed, missing tracking pixels, no "
        f"GA4, that kind of thing. Public signals only, nothing scraped "
        f"from behind logins.\n\n"
        f"I put together a sample pack of {count} {niche} websites and "
        f"attached it (1 CSV + a 1-page PDF showcase). Each entry shows "
        f"the primary issue plus the owner email when it could be "
        f"verified by MX lookup.\n\n"
        f"Since you run {r['agency_name']}, I'd value your honest "
        f"take: is this the kind of pre-qualified list your team would "
        f"actually use for outreach, or is it missing depth? Also open "
        f"to generating a sample for a different niche if this one isn't "
        f"a fit.\n\n"
        f"{FEEDBACK_LINE}\n\n"
        f"{SIGNATURE}"
    )
    cta = "Worth a quick reply with your honest take?"
    return {"subject": subject, "body": body, "cta": cta}
