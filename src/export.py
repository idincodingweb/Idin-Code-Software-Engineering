# src/export.py
"""Export qualified leads ke CSV bertingkat (Starter / Pro / Premium Gold)."""
from __future__ import annotations

import csv
from copy import copy
from pathlib import Path

from src.config import OUTPUT_DIR, TIER_CONFIGS
from src.models import QualifiedLead


_CSV_COLUMNS = [
    "rank",
    "domain",
    "brand",
    "tier",
    "location",
    "niche",
    "category",
    "notes",
    "gold_score",
    "quality_score",
    "data_confidence",
    "pixel_confidence",
    "firmographics_confidence",
    "pixel_detection_method",
    "firmographics_source",
    "detection_notes",
    "data_quality_flags",
    "platform",
    "meta_pixel_in_html",
    "tiktok_pixel_in_html",
    "ga4_in_html",
    "gtm_in_html",
    "google_ads_in_html",
    "pagespeed_mobile",
    "lcp_ms",
    "response_ms",
    "revenue_tier",
    "revenue_score",
    "emails_found",
    "mx_valid",
    "email_status",
    "email_verification_method",
    "running_meta_ads",
    "meta_ads_count",
    "competitors",
    "bi_score",
    "employee_range",
    "location_count",
    "founded_year",
    "social_profiles",
    "tech_signals",
    "gold_reasons",
    "outreach_angle",
    "bi_summary",
]


def export_tiered_csvs(leads: list[QualifiedLead]) -> list[str]:
    """Export ke 4 file: leads_all + 3 tiered."""
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    if not leads:
        print("[export] WARN: No leads to export. Writing empty leads_all.csv for debugging.")
        empty_path = Path(OUTPUT_DIR) / "leads_all.csv"
        _write_csv(empty_path, [])
        return [str(empty_path)]

    sorted_leads = sorted(leads, key=lambda x: x.score, reverse=True)
    for idx, lead in enumerate(sorted_leads, start=1):
        lead.rank = idx

    output_files: list[str] = []

    all_path = Path(OUTPUT_DIR) / "leads_all.csv"
    _write_csv(all_path, sorted_leads)
    print(f"[export] OK leads_all.csv         ({len(sorted_leads)} leads) - INTERNAL")
    output_files.append(str(all_path))

    for tier_cfg in TIER_CONFIGS:
        filtered = [lead for lead in sorted_leads if lead.score >= tier_cfg["min_score"]]
        filtered = filtered[: tier_cfg["limit"]]
        ranked = [_with_local_rank(lead, idx) for idx, lead in enumerate(filtered, 1)]

        tier_path = Path(OUTPUT_DIR) / tier_cfg["filename"]
        _write_csv(tier_path, ranked)
        print(
            f"[export] OK {tier_cfg['filename']:<24} "
            f"({len(ranked):3d} leads, score >= {tier_cfg['min_score']}) - {tier_cfg['label']}"
        )
        output_files.append(str(tier_path))

    return output_files


export_tiered = export_tiered_csvs


def _with_local_rank(lead: QualifiedLead, rank: int) -> QualifiedLead:
    new = copy(lead)
    new.rank = rank
    return new


def _write_csv(path: Path, leads: list[QualifiedLead]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(_CSV_COLUMNS)
        for lead in leads:
            writer.writerow([
                getattr(lead, "rank", 0),
                lead.domain,
                getattr(lead, "brand", "") or "",
                getattr(lead, "tier", "") if getattr(lead, "tier", None) is not None else "",
                lead.location or "",
                lead.niche,
                lead.category or "",
                getattr(lead, "notes", "") or "",
                f"{lead.score:.4f}",
                int(getattr(lead, "quality_score", 0) or 0),
                getattr(lead, "data_confidence", "low") or "low",
                getattr(lead, "pixel_confidence", "low") or "low",
                getattr(lead, "firmographics_confidence", "low") or "low",
                getattr(lead, "pixel_detection_method", "html_regex") or "html_regex",
                getattr(lead, "firmographics_source", "free_enrichment") or "free_enrichment",
                getattr(lead, "detection_notes", "") or "",
                _join(getattr(lead, "data_quality_flags", [])),
                lead.platform or "Unknown",
                _yn(lead.meta_pixel_in_html),
                _yn(getattr(lead, "tiktok_pixel_in_html", False)),
                _yn(lead.ga4_in_html),
                _yn(lead.gtm_in_html),
                _yn(lead.google_ads_in_html),
                lead.pagespeed_score if lead.pagespeed_score is not None else "",
                lead.lcp_ms if lead.lcp_ms is not None else "",
                lead.response_ms if lead.response_ms is not None else "",
                getattr(lead, "revenue_tier", "") or "",
                getattr(lead, "revenue_score", 0) or 0,
                _join(getattr(lead, "emails_found", [])),
                _mx_label(getattr(lead, "mx_valid", None)),
                getattr(lead, "best_email_status", "unknown") or "unknown",
                getattr(lead, "email_verification_method", "none") or "none",
                _bool_label(getattr(lead, "running_meta_ads", None)),
                getattr(lead, "meta_ads_count", "") if getattr(lead, "meta_ads_count", None) is not None else "",
                _join(getattr(lead, "competitors", [])),
                int(getattr(lead, "bi_score", 0) or 0),
                getattr(lead, "employee_range", "") or "",
                int(getattr(lead, "location_count", 0) or 0),
                getattr(lead, "founded_year", "") if getattr(lead, "founded_year", None) is not None else "",
                _join(getattr(lead, "social_profiles", [])),
                _join(getattr(lead, "tech_signals", [])),
                lead.gold_reasons or "",
                lead.outreach_angle or "",
                getattr(lead, "bi_summary", "") or "",
            ])


def _yn(value: bool) -> str:
    return "yes" if value else "no"


def _bool_label(value) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def _mx_label(value) -> str:
    if value is True:
        return "valid"
    if value is False:
        return "invalid"
    return "unknown"


def _join(items) -> str:
    if not items:
        return ""
    return "; ".join(str(item) for item in items)
