# src/analyst.py
"""AI Analyst Layer via kie.ai — OUTPUT BAHASA INDONESIA.

Generate gold_reasons + outreach_angle untuk setiap qualified lead dalam Bahasa Indonesia.
Graceful fallback ke deterministic template kalau API fail.

Config-driven:
- prompt context dari YAML per niche
- fallback reasons/outreach dari YAML per niche
- data quality aware: jangan overclaim kalau confidence rendah
- tier-aware: tier 1 = brand besar, jangan undersell
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from src.bi_enrich import build_bi_summary
from src.config import (
    IDINCODE_API,
    KIE_AI_BASE_URL,
    KIE_AI_MESSAGES_PATH,
    KIE_AI_MODEL,
    KIE_AI_THINKING,
)
from src.config.niche_loader import load_niche_config
from src.models import QualifiedLead
from src.quality_score import sanitize_ai_quality_score


async def enrich_with_ai_analyst(
    leads: list[QualifiedLead],
    *,
    max_retries: int = 2,
) -> list[QualifiedLead]:
    """Enrich semua leads dengan AI-generated reasoning dalam Bahasa Indonesia."""
    if not leads:
        return leads

    if not IDINCODE_API:
        print("[analyst] IDINCODE_API kosong, pakai fallback template (Bahasa Indonesia)")
        return _apply_fallback_to_all(leads)

    print(f"[analyst] Generating AI reasoning (Bahasa Indonesia) untuk {len(leads)} leads via kie.ai...")

    try:
        ai_results = await _call_claude_batch(leads, max_retries=max_retries)
    except Exception as e:  # noqa: BLE001
        print(
            f"[analyst] WARN: AI call failed "
            f"({type(e).__name__}: {e}), pakai fallback"
        )
        return _apply_fallback_to_all(leads)

    enriched: list[QualifiedLead] = []
    matched = 0
    for lead in leads:
        ai_data = ai_results.get(lead.domain)
        if ai_data and isinstance(ai_data, dict):
            lead.gold_reasons = ai_data.get("gold_reasons") or _fallback_reasons(lead)
            lead.outreach_angle = ai_data.get("outreach_angle") or _fallback_outreach(lead)

            ai_q = sanitize_ai_quality_score(ai_data.get("quality_score"))
            if ai_q is not None:
                lead.quality_score = ai_q

            lead.bi_summary = ai_data.get("bi_summary") or build_bi_summary(lead)
            if ai_data.get("gold_reasons"):
                matched += 1
        else:
            lead.gold_reasons = _fallback_reasons(lead)
            lead.outreach_angle = _fallback_outreach(lead)
            lead.bi_summary = build_bi_summary(lead)
        enriched.append(lead)

    print(f"[analyst] OK: AI reasoning generated untuk {matched}/{len(enriched)} leads")
    return enriched


async def _call_claude_batch(
    leads: list[QualifiedLead],
    *,
    max_retries: int,
) -> dict[str, dict[str, Any]]:
    system_prompt = _build_system_prompt(leads)
    user_prompt = _build_user_prompt(leads)

    payload = {
        "model": KIE_AI_MODEL,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt},
        ],
        "thinkingFlag": KIE_AI_THINKING,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {IDINCODE_API}",
        "Content-Type": "application/json",
    }

    url = f"{KIE_AI_BASE_URL.rstrip('/')}{KIE_AI_MESSAGES_PATH}"

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                text = _extract_text_from_response(data)
                if not text:
                    raise ValueError(f"Empty text from response: {str(data)[:300]}")

                parsed = _parse_json_response(text)
                if parsed:
                    return parsed
                raise ValueError(f"Failed to parse JSON. Raw text: {text[:300]}")

            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"[analyst] HTTP {resp.status_code}, retry in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                raise last_error

            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        except httpx.TimeoutException as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"[analyst] Timeout, retry in {wait}s...")
                await asyncio.sleep(wait)
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError("Unknown error in _call_claude_batch")


def _detect_primary_niche(leads: list[QualifiedLead]) -> str:
    counts: dict[str, int] = {}
    for lead in leads:
        niche = (lead.niche or "default").strip()
        counts[niche] = counts.get(niche, 0) + 1
    if not counts:
        return "default"
    return max(counts.items(), key=lambda x: x[1])[0]


def _build_system_prompt(leads: list[QualifiedLead]) -> str:
    primary_niche = _detect_primary_niche(leads)
    cfg = load_niche_config(primary_niche)
    meta = cfg["metadata"]
    analyst = cfg["analyst"]

    return (
        f"Anda adalah analis riset bisnis B2B senior yang spesialis di {meta['industry_label']} "
        f"(tiket khas: {meta['typical_ticket']}, pain point umum: {meta['pain_point']}).\n\n"
        f"Tugas Anda: menganalisis infrastruktur tracking website, sinyal komersial, "
        f"data performa, dan keterbatasan confidence data untuk mengidentifikasi PELUANG BISNIS "
        f"yang bisa dipresentasikan langsung ke brand (bukan ke agency).\n\n"
        f"{analyst['focus']}\n\n"
        f"Output Anda dipakai oleh penyedia data + konsultan untuk dipresentasikan ke brand "
        f"agar mereka memahami posisi mereka dan apa yang bisa diperbaiki.\n\n"
        "ATURAN PENTING:\n"
        "1. Output HANYA berupa JSON valid. Tanpa markdown fences, tanpa preamble, tanpa penjelasan.\n"
        "2. SEMUA isi field (gold_reasons, outreach_angle, bi_summary) WAJIB dalam BAHASA INDONESIA.\n"
        "3. Untuk setiap domain, hasilkan:\n"
        "   - gold_reasons (1-2 kalimat Bahasa Indonesia): KENAPA brand ini layak diberi insight. Sebutkan gap spesifik dengan dampak bisnis nyata.\n"
        "   - outreach_angle (1 kalimat Bahasa Indonesia): Subject line email atau opening hook yang siap dipakai. Tone: profesional, friendly, tidak sok jual.\n"
        "   - quality_score (integer 0-100): seberapa potensial brand ini sebagai prospect data+konsultasi. Pakai base_score sebagai anchor, adjust dalam ~15 poin.\n"
        "   - bi_summary (1-2 kalimat Bahasa Indonesia): pembacaan business intelligence ringkas dari sinyal yang ada.\n"
        "4. Tone: profesional, data-driven, no fluff, no buzzword. Bahasa Indonesia yang natural (bukan terjemahan kaku).\n"
        "5. PENTING: Jangan overclaim 'missing tracking' kalau pixel_confidence rendah. Pemindaian HTML statis bisa miss tag yang di-load via JavaScript.\n"
        "6. PENTING: Perlakukan estimasi karyawan/revenue sebagai indikatif kalau firmographics_confidence rendah.\n"
        "7. PENTING: Kalau tier=1 (brand besar) dan firmographics terdeteksi kecil, ASUMSIKAN itu false negative — brand tier 1 di Indonesia (Erigo, Wardah, Skintific, dll) biasanya punya >100 karyawan dan revenue besar. Tulis bi_summary dengan asumsi brand established, bukan brand mikro.\n"
        f"8. {analyst['mature_business_note']}\n"
        "9. Format response WAJIB persis seperti ini:\n"
        "{\n"
        '  "results": {\n'
        '    "domain1.com": {"gold_reasons": "...", "outreach_angle": "...", "quality_score": 0, "bi_summary": "..."},\n'
        '    "domain2.com": {"gold_reasons": "...", "outreach_angle": "...", "quality_score": 0, "bi_summary": "..."}\n'
        "  }\n"
        "}"
    )


def _build_user_prompt(leads: list[QualifiedLead]) -> str:
    lines = [
        "Analisis brand-brand berikut. Untuk setiap brand, hasilkan gold_reasons, outreach_angle, "
        "quality_score (0-100), dan bi_summary — SEMUA dalam BAHASA INDONESIA. Return JSON saja.\n",
        "Data per brand:",
    ]

    for lead in leads:
        pixels = []
        if lead.meta_pixel_in_html:
            pixels.append("Meta")
        if lead.tiktok_pixel_in_html:
            pixels.append("TikTok")
        if lead.ga4_in_html:
            pixels.append("GA4")
        if lead.gtm_in_html:
            pixels.append("GTM")
        if lead.google_ads_in_html:
            pixels.append("GoogleAds")
        pixels_str = ",".join(pixels) if pixels else "NONE"

        ps_str = f"{lead.pagespeed_score}" if lead.pagespeed_score is not None else "N/A"
        lcp_str = f"{lead.lcp_ms}ms" if lead.lcp_ms is not None else "N/A"
        rt_str = f"{lead.response_ms}ms" if lead.response_ms is not None else "N/A"

        emails_n = len(getattr(lead, "emails_found", []) or [])
        mx = getattr(lead, "mx_valid", None)
        mx_str = "yes" if mx is True else "no" if mx is False else "N/A"
        ads = getattr(lead, "running_meta_ads", None)
        ads_str = "yes" if ads is True else "no" if ads is False else "N/A"
        social = getattr(lead, "social_profiles", []) or []
        tech = getattr(lead, "tech_signals", []) or []
        founded = getattr(lead, "founded_year", None)
        brand = (getattr(lead, "brand", None) or "").strip() or "N/A"
        tier = getattr(lead, "tier", None)
        notes = (getattr(lead, "notes", None) or "").strip() or "N/A"
        pixel_conf = getattr(lead, "pixel_confidence", "low") or "low"
        firmo_conf = getattr(lead, "firmographics_confidence", "low") or "low"
        data_conf = getattr(lead, "data_confidence", "low") or "low"
        pixel_method = getattr(lead, "pixel_detection_method", "html_regex") or "html_regex"
        firmo_source = getattr(lead, "firmographics_source", "free_enrichment") or "free_enrichment"
        detection_notes = (getattr(lead, "detection_notes", None) or "").strip() or "N/A"
        data_quality_flags = getattr(lead, "data_quality_flags", []) or []

        lines.append(
            f"- domain={lead.domain} | brand={brand} | niche={lead.niche} | "
            f"category={lead.category or 'N/A'} | "
            f"tier={tier if tier is not None else 'N/A'} | "
            f"location={lead.location or 'N/A'} | "
            f"platform={lead.platform or 'Unknown'} | "
            f"pixels_in_html=[{pixels_str}] | "
            f"pixel_confidence={pixel_conf} | "
            f"pixel_detection_method={pixel_method} | "
            f"firmographics_confidence={firmo_conf} | "
            f"firmographics_source={firmo_source} | "
            f"data_confidence={data_conf} | "
            f"pagespeed_mobile={ps_str} | lcp={lcp_str} | response_time={rt_str} | "
            f"gold_score={lead.score:.2f} | base_score={int(getattr(lead, 'quality_score', 0) or 0)} | "
            f"emails_found={emails_n} | mx_valid={mx_str} | running_meta_ads={ads_str} | "
            f"meta_ads_count={getattr(lead, 'meta_ads_count', None) if getattr(lead, 'meta_ads_count', None) is not None else 'N/A'} | "
            f"revenue_tier={getattr(lead, 'revenue_tier', 'unknown')} | "
            f"employees={getattr(lead, 'employee_range', 'unknown')} | "
            f"locations={getattr(lead, 'location_count', 0)} | "
            f"founded={founded if founded else 'N/A'} | "
            f"social=[{','.join(social) if social else 'NONE'}] | "
            f"tech=[{','.join(tech) if tech else 'NONE'}] | "
            f"data_quality_flags=[{','.join(str(x) for x in data_quality_flags) if data_quality_flags else 'NONE'}] | "
            f"detection_notes={detection_notes} | "
            f"notes={notes}"
        )

    lines.append(
        "\nIngat: output HANYA JSON object, tanpa markdown fences, tanpa penjelasan. SEMUA isi field dalam Bahasa Indonesia."
    )
    return "\n".join(lines)


def _extract_text_from_response(data: dict[str, Any]) -> str:
    content = data.get("content")
    if not isinstance(content, list) or not content:
        return ""

    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text", "")
            if isinstance(text, str) and text:
                return text

    first = content[0]
    if isinstance(first, dict):
        text = first.get("text", "")
        if isinstance(text, str):
            return text

    return ""


def _parse_json_response(text: str) -> dict[str, dict[str, Any]]:
    if not text:
        return {}

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    results = data.get("results", {})
    if not isinstance(results, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for domain, payload in results.items():
        if not isinstance(payload, dict):
            continue
        entry: dict[str, Any] = {
            "gold_reasons": str(payload.get("gold_reasons", "")).strip(),
            "outreach_angle": str(payload.get("outreach_angle", "")).strip(),
            "bi_summary": str(payload.get("bi_summary", "")).strip(),
        }
        if "quality_score" in payload:
            entry["quality_score"] = payload.get("quality_score")
        normalized[domain] = entry
    return normalized


def _apply_fallback_to_all(leads: list[QualifiedLead]) -> list[QualifiedLead]:
    for lead in leads:
        lead.gold_reasons = _fallback_reasons(lead)
        lead.outreach_angle = _fallback_outreach(lead)
        lead.bi_summary = build_bi_summary(lead)
    return leads


def _missing_tracking_items(lead: QualifiedLead) -> list[str]:
    items = []
    if not lead.meta_pixel_in_html:
        items.append("Meta Pixel")
    if not lead.tiktok_pixel_in_html:
        items.append("TikTok Pixel")
    if not lead.ga4_in_html:
        items.append("GA4")
    if not lead.gtm_in_html:
        items.append("GTM")
    if not lead.google_ads_in_html:
        items.append("Google Ads tag")
    return items


def _template_context(lead: QualifiedLead) -> dict[str, Any]:
    brand = (getattr(lead, "brand", None) or "").strip()
    domain_label = brand or lead.domain.replace("www.", "").split(".")[0].title()
    missing = _missing_tracking_items(lead)
    social = getattr(lead, "social_profiles", []) or []
    tech = getattr(lead, "tech_signals", []) or []
    flags = getattr(lead, "data_quality_flags", []) or []

    return {
        "domain": lead.domain,
        "brand": domain_label,
        "niche": getattr(lead, "niche", "default") or "default",
        "category": getattr(lead, "category", None) or "N/A",
        "tier": getattr(lead, "tier", None) if getattr(lead, "tier", None) is not None else "N/A",
        "platform": getattr(lead, "platform", None) or "Unknown",
        "revenue_tier": getattr(lead, "revenue_tier", "unknown"),
        "employee_range": getattr(lead, "employee_range", "unknown"),
        "location_count": getattr(lead, "location_count", 0) or 0,
        "missing_tracking_count": len(missing),
        "missing_tracking_items": ", ".join(missing[:4]) if missing else "tidak ada",
        "social_profiles_count": len(social),
        "social_profiles": ", ".join(social[:5]) if social else "TIDAK ADA",
        "tech_signals_count": len(tech),
        "tech_signals": ", ".join(tech[:5]) if tech else "TIDAK ADA",
        "pagespeed_score": getattr(lead, "pagespeed_score", None) if getattr(lead, "pagespeed_score", None) is not None else "N/A",
        "response_ms": getattr(lead, "response_ms", None) if getattr(lead, "response_ms", None) is not None else "N/A",
        "emails_found_count": len(getattr(lead, "emails_found", []) or []),
        "mx_valid": getattr(lead, "mx_valid", None),
        "running_meta_ads": getattr(lead, "running_meta_ads", None),
        "pixel_confidence": getattr(lead, "pixel_confidence", "low") or "low",
        "firmographics_confidence": getattr(lead, "firmographics_confidence", "low") or "low",
        "data_confidence": getattr(lead, "data_confidence", "low") or "low",
        "pixel_detection_method": getattr(lead, "pixel_detection_method", "html_regex") or "html_regex",
        "firmographics_source": getattr(lead, "firmographics_source", "free_enrichment") or "free_enrichment",
        "detection_notes": getattr(lead, "detection_notes", "") or "",
        "data_quality_flags": ", ".join(str(x) for x in flags) if flags else "TIDAK ADA",
    }


def _field_value(lead: QualifiedLead, field: str) -> Any:
    if field == "missing_tracking_count":
        return len(_missing_tracking_items(lead))
    if field == "social_profiles_count":
        return len(getattr(lead, "social_profiles", []) or [])
    if field == "emails_found_count":
        return len(getattr(lead, "emails_found", []) or [])
    return getattr(lead, field, None)


def _to_number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _matches_condition(lead: QualifiedLead, condition: dict[str, Any]) -> bool:
    field = str(condition.get("field", "")).strip()
    op = str(condition.get("op", "eq")).strip().lower()
    expected = condition.get("value")
    actual = _field_value(lead, field)

    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        values = expected if isinstance(expected, list) else [expected]
        return actual in values
    if op == "not_in":
        values = expected if isinstance(expected, list) else [expected]
        return actual not in values
    if op == "contains":
        if isinstance(actual, list):
            return expected in actual
        if isinstance(actual, str):
            return str(expected).lower() in actual.lower()
        return False
    if op == "truthy":
        return bool(actual)
    if op == "falsy":
        return not bool(actual)

    actual_num = _to_number(actual)
    expected_num = _to_number(expected)

    if op == "gte":
        return actual_num is not None and expected_num is not None and actual_num >= expected_num
    if op == "gt":
        return actual_num is not None and expected_num is not None and actual_num > expected_num
    if op == "lte":
        return actual_num is not None and expected_num is not None and actual_num <= expected_num
    if op == "lt":
        return actual_num is not None and expected_num is not None and actual_num < expected_num

    return False


def _matches_all(lead: QualifiedLead, conditions: list[dict[str, Any]]) -> bool:
    return all(_matches_condition(lead, cond) for cond in conditions)


def _render_template(template: str, lead: QualifiedLead) -> str:
    ctx = _template_context(lead)
    try:
        return template.format(**ctx).strip()
    except Exception:
        return template.strip()


def _fallback_reasons(lead: QualifiedLead) -> str:
    cfg = load_niche_config(getattr(lead, "niche", "default") or "default")
    rules = cfg["analyst"].get("fallback_reasons_rules", [])

    reasons: list[str] = []
    for rule in rules:
        conditions = list(rule.get("conditions") or [])
        template = str(rule.get("template", "")).strip()
        if not template:
            continue
        if conditions and _matches_all(lead, conditions):
            reasons.append(_render_template(template, lead))

    if not reasons:
        return (
            "Peluang terbatas — infrastruktur terlihat sehat dari sinyal publik. "
            "Penilaian ini konservatif karena visibility tracking dan firmografi dari "
            "scan publik belum lengkap. Direkomendasikan validasi manual sebelum outreach."
        )

    return " ".join(dict.fromkeys(reasons))


def _fallback_outreach(lead: QualifiedLead) -> str:
    cfg = load_niche_config(getattr(lead, "niche", "default") or "default")
    rules = cfg["analyst"].get("fallback_outreach_rules", [])

    ordered_rules = sorted(rules, key=lambda item: int(item.get("priority", 999)))
    for rule in ordered_rules:
        conditions = list(rule.get("conditions") or [])
        template = str(rule.get("template", "")).strip()
        if not template:
            continue
        if conditions and _matches_all(lead, conditions):
            return _render_template(template, lead)

    brand = _template_context(lead)["brand"]
    return f"Subject: Beberapa insight singkat tentang website {brand} (5 menit baca)"