# src/analyst.py
"""Claude AI Analyst Layer via kie.ai (Anthropic-native format).

Generate gold_reasons + outreach_angle untuk setiap qualified lead.
Graceful fallback ke deterministic template kalau API fail.
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
from src.models import QualifiedLead
from src.quality_score import sanitize_ai_quality_score


# ============================================================
# Public API
# ============================================================
async def enrich_with_ai_analyst(
    leads: list[QualifiedLead],
    *,
    max_retries: int = 2,
) -> list[QualifiedLead]:
    """Enrich SEMUA leads dengan AI-generated gold_reasons + outreach_angle."""
    if not leads:
        return leads

    if not IDINCODE_API:
        print("[analyst] IDINCODE_API kosong, pakai fallback template")
        return _apply_fallback_to_all(leads)

    print(f"[analyst] Generating AI reasoning untuk {len(leads)} leads via kie.ai...")

    try:
        ai_results = await _call_claude_batch(leads, max_retries=max_retries)
    except Exception as e:  # noqa: BLE001
        print(
            f"[analyst] WARN: Claude call failed "
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


# ============================================================
# kie.ai API call (Anthropic-native format)
# ============================================================
async def _call_claude_batch(
    leads: list[QualifiedLead],
    *,
    max_retries: int,
) -> dict[str, dict[str, Any]]:
    """Call kie.ai endpoint /claude/v1/messages (Anthropic-native)."""
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
                last_error = RuntimeError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
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


# ============================================================
# Dynamic Prompt Builder (per-niche context)
# ============================================================
_NICHE_CONTEXT: dict[str, dict[str, str]] = {
    "medical_high_ticket": {
        "industry_label": "high-ticket medical & aesthetic clinics",
        "typical_ticket": "$3,000-$30,000 per case",
        "pain_point": "consult-to-book conversion, attribution clarity, ROAS visibility",
    },
    "cosmetic_dentistry": {
        "industry_label": "cosmetic & implant dentistry practices",
        "typical_ticket": "$3,000-$30,000 per case",
        "pain_point": "consult-to-book conversion, attribution clarity",
    },
    "premium_orthodontics": {
        "industry_label": "premium orthodontics & clear aligner clinics",
        "typical_ticket": "$3,000-$8,000 per patient",
        "pain_point": "adult market competition, patient LTV tracking",
    },
    "weight_loss_glp1": {
        "industry_label": "weight loss & GLP-1 telehealth clinics",
        "typical_ticket": "$200-$500/month subscription",
        "pain_point": "telehealth conversion gaps, retention funnels",
    },
    "premium_hair_restoration": {
        "industry_label": "premium hair restoration & transplant clinics",
        "typical_ticket": "$8,000-$15,000 per procedure",
        "pain_point": "high CAC, emotional + surgical decision support",
    },
    "fashion_apparel": {
        "industry_label": "direct-to-consumer fashion & apparel brands",
        "typical_ticket": "$20-$250 average order value",
        "pain_point": "ROAS efficiency, retention, attribution gaps, marketplace-to-website funnel leakage",
    },
    "fashion_marketplace": {
        "industry_label": "fashion marketplace & multi-brand retail businesses",
        "typical_ticket": "$20-$300 average order value",
        "pain_point": "channel attribution, repeat purchase, CRM capture from marketplace traffic",
    },
    "fashion_retail": {
        "industry_label": "fashion retail & omnichannel commerce brands",
        "typical_ticket": "$25-$300 average order value",
        "pain_point": "omnichannel attribution, catalog efficiency, paid media scaling",
    },
    "default": {
        "industry_label": "growth-stage businesses",
        "typical_ticket": "$1,000-$10,000 per customer or retainer equivalent",
        "pain_point": "lead-to-close conversion, marketing attribution",
    },
}


def _detect_primary_niche(leads: list[QualifiedLead]) -> str:
    """Cari niche paling umum di batch."""
    counts: dict[str, int] = {}
    for lead in leads:
        niche = lead.niche or "default"
        counts[niche] = counts.get(niche, 0) + 1
    if not counts:
        return "default"
    return max(counts.items(), key=lambda x: x[1])[0]


def _is_fashion_lead(lead: QualifiedLead) -> bool:
    niche = (lead.niche or "").lower()
    category = (lead.category or "").lower()
    text = f"{niche} {category}"
    return any(
        keyword in text
        for keyword in (
            "fashion",
            "apparel",
            "footwear",
            "streetwear",
            "batik",
            "hijab",
            "women_fashion",
            "mens_formal",
            "activewear",
            "marketplace",
            "retail",
        )
    )


def _batch_is_fashion(leads: list[QualifiedLead]) -> bool:
    if not leads:
        return False
    fashion_count = sum(1 for lead in leads if _is_fashion_lead(lead))
    return fashion_count >= max(1, len(leads) // 2)


def _build_system_prompt(leads: list[QualifiedLead]) -> str:
    """Build dynamic system prompt berdasarkan niche dominant di batch."""
    primary_niche = _detect_primary_niche(leads)
    ctx = _NICHE_CONTEXT.get(primary_niche, _NICHE_CONTEXT["default"])

    if _batch_is_fashion(leads):
        sales_opportunity_hint = (
            "Focus on e-commerce growth opportunities: missing attribution stack, "
            "paid social readiness, CRM capture gaps, retention setup, and conversion "
            "friction that a performance marketing agency can fix quickly."
        )
        mature_business_line = (
            "If a brand already has mature tracking, strong social presence, and paid "
            "media signals, mark it as lower urgency unless there is a clear scale or "
            "retention opportunity."
        )
    else:
        sales_opportunity_hint = (
            "Focus on website tracking infrastructure, conversion friction, and revenue "
            "capture gaps that a marketing agency can pitch."
        )
        mature_business_line = (
            "If a clinic/business already has mature infra, honestly say "
            "'limited opportunity' and give a lower quality_score."
        )

    return (
        f"You are an expert B2B sales analyst specializing in digital marketing "
        f"for {ctx['industry_label']} (typical deal size: {ctx['typical_ticket']}, "
        f"common pain point: {ctx['pain_point']}).\n\n"
        f"Your job: analyze website tracking infrastructure, commercial signals, and "
        f"performance data to identify SALES OPPORTUNITIES that marketing agencies can pitch.\n\n"
        f"Your output is used by agencies to cold-pitch services to these businesses. "
        f"Be SPECIFIC, ACTIONABLE, and slightly URGENT.\n\n"
        f"{sales_opportunity_hint}\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON. No markdown fences, no preamble, no explanation.\n"
        "2. For each domain, generate:\n"
        "   - gold_reasons (1-2 sentences): WHY this is a hot lead. Reference "
        "specific gaps with concrete impact (revenue, attribution clarity, ROAS, retention, or scale).\n"
        "   - outreach_angle (1 sentence): A cold email subject line OR opening "
        "hook an agency can use immediately. Make it pattern-interrupting.\n"
        "   - quality_score (integer 0-100): how good a SALES PROSPECT this lead "
        "is for an agency. Higher = bigger opportunity AND easier to close. "
        "Weigh tracking/perf gaps (opportunity), contactability (email + MX), and "
        "buying signals (active ads, revenue band, social presence, tier if provided). "
        "Use the provided base_score as an anchor and adjust within ~15 points.\n"
        "   - bi_summary (1-2 sentences): concise business-intelligence read of the "
        "company (size, maturity, tech stack, footprint) from the given signals.\n"
        "3. Tone: confident, data-driven, no fluff, no buzzwords.\n"
        f"4. {mature_business_line}\n"
        "5. Response format MUST be exactly:\n"
        "{\n"
        '  "results": {\n'
        '    "domain1.com": {"gold_reasons": "...", "outreach_angle": "...", '
        '"quality_score": 0, "bi_summary": "..."},\n'
        '    "domain2.com": {"gold_reasons": "...", "outreach_angle": "...", '
        '"quality_score": 0, "bi_summary": "..."}\n'
        "  }\n"
        "}"
    )


def _build_user_prompt(leads: list[QualifiedLead]) -> str:
    lines = [
        "Analyze these businesses. For each, generate gold_reasons, "
        "outreach_angle, quality_score (0-100) & bi_summary. Return JSON only.\n",
        "Data per business:",
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
        rt_str = f"{lead.response_ms}ms" if lead.response_ms else "N/A"

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
        meta_ads_count = getattr(lead, "meta_ads_count", None)

        lines.append(
            f"- domain={lead.domain} | brand={brand} | niche={lead.niche} | "
            f"category={lead.category or 'N/A'} | tier={tier if tier is not None else 'N/A'} | "
            f"location={lead.location or 'N/A'} | "
            f"platform={lead.platform or 'Unknown'} | "
            f"pixels_in_html=[{pixels_str}] | "
            f"pagespeed_mobile={ps_str} | lcp={lcp_str} | response_time={rt_str} | "
            f"gold_score={lead.score:.2f} | base_score={int(getattr(lead, 'quality_score', 0) or 0)} | "
            f"emails_found={emails_n} | mx_valid={mx_str} | running_meta_ads={ads_str} | "
            f"meta_ads_count={meta_ads_count if meta_ads_count is not None else 'N/A'} | "
            f"revenue_tier={getattr(lead, 'revenue_tier', 'unknown')} | "
            f"employees={getattr(lead, 'employee_range', 'unknown')} | "
            f"locations={getattr(lead, 'location_count', 0)} | "
            f"founded={founded if founded else 'N/A'} | "
            f"social=[{','.join(social) if social else 'NONE'}] | "
            f"tech=[{','.join(tech) if tech else 'NONE'}] | "
            f"notes={notes}"
        )

    lines.append(
        "\nRemember: output ONLY the JSON object, no markdown fences, no explanation."
    )
    return "\n".join(lines)


# ============================================================
# Response parsing (Anthropic-native format)
# ============================================================
def _extract_text_from_response(data: dict[str, Any]) -> str:
    """Extract text dari Anthropic-native response format."""
    content = data.get("content")
    if not isinstance(content, list) or not content:
        return ""

    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
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
    """Parse JSON dari response. Strip markdown fences kalau ada (defensive)."""
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


# ============================================================
# Fallback (deterministic, no API needed)
# ============================================================
def _apply_fallback_to_all(leads: list[QualifiedLead]) -> list[QualifiedLead]:
    for lead in leads:
        lead.gold_reasons = _fallback_reasons(lead)
        lead.outreach_angle = _fallback_outreach(lead)
        lead.bi_summary = build_bi_summary(lead)
    return leads


def _missing_tracking_stack(lead: QualifiedLead) -> list[str]:
    missing = []
    if not lead.meta_pixel_in_html:
        missing.append("Meta Pixel")
    if not lead.tiktok_pixel_in_html and _is_fashion_lead(lead):
        missing.append("TikTok Pixel")
    if not lead.ga4_in_html:
        missing.append("GA4")
    if not lead.gtm_in_html:
        missing.append("GTM")
    if not lead.google_ads_in_html:
        missing.append("Google Ads tag")
    return missing


def _fallback_reasons(lead: QualifiedLead) -> str:
    reasons: list[str] = []
    missing = _missing_tracking_stack(lead)
    social = getattr(lead, "social_profiles", []) or []
    tech = getattr(lead, "tech_signals", []) or []
    tier = getattr(lead, "tier", None)
    revenue_tier = (getattr(lead, "revenue_tier", "") or "").strip().lower()
    running_ads = getattr(lead, "running_meta_ads", None)

    if _is_fashion_lead(lead):
        if len(missing) >= 3:
            reasons.append(
                f"Missing {len(missing)} key tracking signals "
                f"({', '.join(missing[:4])}) - weak attribution for paid social, retargeting, and catalog optimization."
            )
        elif missing:
            reasons.append(
                f"Missing {', '.join(missing[:3])} - incomplete e-commerce attribution stack."
            )

        if running_ads is False and revenue_tier in ("large", "enterprise"):
            reasons.append(
                "Revenue footprint looks meaningful but active Meta ads were not detected - clear paid social scale opportunity."
            )

        if len(social) <= 1:
            reasons.append(
                "Thin social footprint detected - likely room to tighten content-to-conversion loops and creator amplification."
            )

        if lead.platform and lead.platform.lower() in ("wordpress", "woocommerce", "shopify", "unknown"):
            reasons.append(
                "Website stack looks serviceable but still easy to onboard for tracking, funnel, and CRM fixes."
            )

        if "klaviyo" not in tech and "mailchimp" not in tech and revenue_tier in ("large", "enterprise"):
            reasons.append(
                "No obvious lifecycle/CRM signal detected on-site - repeat purchase and retention automation may be underbuilt."
            )

        if tier == 1:
            reasons.append(
                "Tier 1 target with brand maturity signals - bigger upside if attribution and paid media execution are tightened."
            )
    else:
        if len(missing) >= 3:
            reasons.append(
                f"Missing {len(missing)} key tracking pixels "
                f"({', '.join(missing[:3])}) - major retargeting & attribution gap."
            )
        elif missing:
            reasons.append(
                f"Missing {', '.join(missing[:3])} - incomplete attribution stack."
            )

        if lead.pagespeed_score is not None:
            if lead.pagespeed_score < 50:
                reasons.append(
                    f"Mobile PageSpeed {lead.pagespeed_score}/100 - high bounce risk on mobile traffic."
                )
            elif lead.pagespeed_score < 70:
                reasons.append(
                    f"Mobile PageSpeed {lead.pagespeed_score}/100 - room for conversion uplift."
                )

        if lead.response_ms and lead.response_ms > 3000:
            reasons.append(
                f"Server response {lead.response_ms}ms - signals hosting/tech debt."
            )

        if lead.platform and lead.platform.lower() in ("wordpress", "woocommerce"):
            reasons.append(
                "WordPress stack - easy to onboard for tracking & speed fixes."
            )

    if not reasons:
        return (
            "Limited opportunity - infrastructure looks healthy. "
            "Consider for retention or scaling plays only."
        )

    return " ".join(reasons[:4])


def _fallback_outreach(lead: QualifiedLead) -> str:
    brand = (getattr(lead, "brand", None) or "").strip()
    domain_label = brand or lead.domain.replace("www.", "").split(".")[0].title()
    missing_pixels = _missing_tracking_stack(lead)

    if _is_fashion_lead(lead):
        tier = getattr(lead, "tier", None)
        revenue_tier = (getattr(lead, "revenue_tier", "") or "").strip().lower()
        running_ads = getattr(lead, "running_meta_ads", None)
        social = getattr(lead, "social_profiles", []) or []

        if len(missing_pixels) >= 2:
            return (
                f"Subject: Found {len(missing_pixels)} attribution gaps on {domain_label}'s store - worth a quick ROAS audit?"
            )

        if running_ads is False and revenue_tier in ("large", "enterprise"):
            return (
                f"Subject: {domain_label} looks ready for paid social scale - but Meta demand capture seems missing"
            )

        if len(social) <= 1:
            return (
                f"Subject: Quick thought on turning {domain_label}'s social traffic into more first-party revenue"
            )

        if tier == 1:
            return (
                f"Subject: One revenue leak I suspect on {domain_label}'s website funnel"
            )

        return (
            f"Subject: 3 growth gaps I spotted on {domain_label}'s e-commerce funnel"
        )

    if len(missing_pixels) >= 2:
        return (
            f"Subject: Found {len(missing_pixels)} tracking gaps on "
            f"{domain_label}'s site - worth a 15-min chat?"
        )

    if lead.pagespeed_score is not None and lead.pagespeed_score < 50:
        return (
            f"Subject: {domain_label}'s mobile site loads at "
            f"{lead.pagespeed_score}/100 - here's what it's costing you"
        )

    if lead.response_ms and lead.response_ms > 3000:
        return (
            f"Subject: Quick note about {domain_label}'s site speed "
            f"(I think you're losing leads)"
        )

    return (
        f"Subject: 3 quick wins I spotted for {domain_label} "
        f"(takes 5 min to read)"
    )