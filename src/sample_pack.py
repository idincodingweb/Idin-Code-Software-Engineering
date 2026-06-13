"""Sample Pack Generator — buat showcase pack siap lampir ke email agency.

Built by Idin Iskandar.

Tujuan:
    Ambil top-N leads dari pipeline LEADS (run.py output), filter yang punya
    masalah paling jelas (slow site / missing pixel / low score), bungkus
    jadi 2 file siap kirim:

      output/sample_pack/<niche>_sample_<ts>.csv  (clean CSV, kolom rapi)
      output/sample_pack/<niche>_sample_<ts>.pdf  (cover + per-lead summary)

Dipakai sebagai "alat pancing" buat outreach ke agency luar (US/UK/AU/EU).
Strategi: kirim sample 5-10 leads -> kalau agency tertarik baru jual paket
penuh (100/500/subs).

Public API:
    build_sample_pack(rows, *, niche_label=None, out_dir=..., top_n=10) -> dict
        rows: list[dict] dari CSV reader (leads_all.csv / leads_premium_gold.csv)
        return: {"csv": path, "pdf": path|None, "count": n, "niche": str}

Backward-compat: kalau reportlab gak ada, CSV tetap di-generate, PDF di-skip
dengan warning (gak crash).
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
    )
    _HAS_REPORTLAB = True
except ImportError:  # pragma: no cover
    _HAS_REPORTLAB = False


# ============================================================
# Public columns for the "clean" sample CSV
# (subset of leads_all.csv yang aman dikirim ke prospek agency)
# ============================================================
SAMPLE_CSV_COLUMNS = [
    "rank",
    "domain",
    "niche",
    "location",
    "opportunity_score",
    "pagespeed_mobile",
    "lcp_ms",
    "meta_pixel",
    "ga4",
    "google_ads",
    "platform",
    "primary_issue",
    "owner_email",
    "mx_status",
]


# ============================================================
# Filtering / ranking
# ============================================================
def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in ("", None) else default
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(float(v)) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def _is_no(v: Any) -> bool:
    """Mark 'no'/'false'/'0' as a present GAP (so we want it)."""
    return str(v).strip().lower() in ("no", "false", "0", "")


def _problem_count(row: dict) -> int:
    """Higher = more obvious 'sample-worthy' issues."""
    score = 0
    ps = _safe_int(row.get("pagespeed_mobile"))
    if ps is not None and ps < 60:
        score += 2
    lcp = _safe_int(row.get("lcp_ms"))
    if lcp is not None and lcp > 3500:
        score += 2
    if _is_no(row.get("meta_pixel_in_html")):
        score += 1
    if _is_no(row.get("ga4_in_html")):
        score += 1
    if _is_no(row.get("google_ads_in_html")):
        score += 1
    return score


def _primary_issue(row: dict) -> str:
    ps = _safe_int(row.get("pagespeed_mobile"))
    lcp = _safe_int(row.get("lcp_ms"))
    if lcp is not None and lcp > 3500:
        return f"Slow LCP {lcp}ms (>3.5s mobile)"
    if ps is not None and ps < 50:
        return f"Poor PageSpeed mobile ({ps}/100)"
    if _is_no(row.get("meta_pixel_in_html")):
        return "Missing Meta Pixel (no retargeting infra)"
    if _is_no(row.get("ga4_in_html")):
        return "Missing GA4 (no analytics)"
    if _is_no(row.get("google_ads_in_html")):
        return "No Google Ads conversion tag"
    if ps is not None and ps < 70:
        return f"Below-average PageSpeed ({ps}/100)"
    return "Multiple optimization opportunities"


def _first_email(row: dict) -> str:
    raw = (row.get("emails_found") or "").strip()
    if not raw:
        return ""
    # CSV stores them as "a; b; c"
    parts = [p.strip() for p in raw.replace(",", ";").split(";") if p.strip()]
    return parts[0] if parts else ""


def _mx_status(row: dict) -> str:
    v = (row.get("mx_valid") or "").strip().lower()
    if v in ("valid", "yes", "true", "1"):
        return "verified"
    if v in ("invalid", "no", "false", "0"):
        return "invalid"
    return "unknown"


# ============================================================
# Public builder
# ============================================================
def build_sample_pack(
    rows: Iterable[dict],
    *,
    niche_label: Optional[str] = None,
    out_dir: str = "output/sample_pack",
    top_n: int = 10,
    min_score: float = 0.50,
) -> dict:
    """Build CSV + PDF sample pack.

    rows: list[dict] (dari csv.DictReader)
    """
    rows_list = [r for r in rows if (r.get("domain") or "").strip()]
    if not rows_list:
        print("[sample-pack] WARN: no rows provided")
        return {"csv": None, "pdf": None, "count": 0, "niche": niche_label or "mixed"}

    # Filter by min score (kolom CSV = gold_score)
    filtered = [r for r in rows_list if _safe_float(r.get("gold_score")) >= min_score]
    if not filtered:
        # Fallback: tetap pakai semua row (mungkin score-nya 0 karna belum AI)
        filtered = rows_list

    # Optional niche filter
    if niche_label:
        nl = niche_label.strip().lower().replace("_", " ")
        narrowed = [
            r for r in filtered
            if nl in (r.get("niche", "") or "").lower().replace("_", " ")
        ]
        if narrowed:
            filtered = narrowed

    # Rank: gold_score desc, then problem_count desc
    filtered.sort(
        key=lambda r: (_safe_float(r.get("gold_score")), _problem_count(r)),
        reverse=True,
    )
    selected = filtered[:max(1, top_n)]

    # Derive niche label if not given
    if not niche_label:
        niches = {(r.get("niche") or "").strip() for r in selected if r.get("niche")}
        niche_label = (
            next(iter(niches)) if len(niches) == 1 else "mixed"
        )
    niche_slug = _slug(niche_label)

    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = str(Path(out_dir) / f"{niche_slug}_sample_{ts}.csv")
    pdf_path = str(Path(out_dir) / f"{niche_slug}_sample_{ts}.pdf")

    _write_sample_csv(csv_path, selected)
    print(f"[sample-pack] OK wrote {len(selected)} rows -> {csv_path}")

    pdf_out: Optional[str] = None
    if _HAS_REPORTLAB:
        try:
            _write_sample_pdf(pdf_path, selected, niche_label=niche_label)
            pdf_out = pdf_path
            print(f"[sample-pack] OK wrote PDF -> {pdf_path}")
        except Exception as e:  # noqa: BLE001
            print(f"[sample-pack] WARN PDF failed: {type(e).__name__}: {e}")
    else:
        print("[sample-pack] SKIP PDF: reportlab not installed (pip install reportlab)")

    return {
        "csv": csv_path,
        "pdf": pdf_out,
        "count": len(selected),
        "niche": niche_label,
    }


# ============================================================
# CSV writer
# ============================================================
def _write_sample_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SAMPLE_CSV_COLUMNS)
        w.writeheader()
        for i, r in enumerate(rows, start=1):
            w.writerow({
                "rank": i,
                "domain": r.get("domain", ""),
                "niche": r.get("niche", ""),
                "location": r.get("location", ""),
                "opportunity_score": r.get("gold_score", ""),
                "pagespeed_mobile": r.get("pagespeed_mobile", ""),
                "lcp_ms": r.get("lcp_ms", ""),
                "meta_pixel": r.get("meta_pixel_in_html", ""),
                "ga4": r.get("ga4_in_html", ""),
                "google_ads": r.get("google_ads_in_html", ""),
                "platform": r.get("platform", ""),
                "primary_issue": _primary_issue(r),
                "owner_email": _first_email(r),
                "mx_status": _mx_status(r),
            })


# ============================================================
# PDF writer
# ============================================================
def _write_sample_pdf(path: str, rows: list[dict], *, niche_label: str) -> None:
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Sample Lead Pack — {niche_label}",
        author="Idincode Apex Market Intelligence",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1c", parent=styles["Heading1"], fontSize=22,
        textColor=colors.HexColor("#0f4c81"), spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "h2c", parent=styles["Heading2"], fontSize=13,
        textColor=colors.HexColor("#0f4c81"),
        spaceBefore=10, spaceAfter=4,
    )
    body = ParagraphStyle(
        "bd", parent=styles["BodyText"], fontSize=10, leading=14,
    )
    small = ParagraphStyle(
        "sm", parent=styles["BodyText"], fontSize=8,
        textColor=colors.grey,
    )

    story: list = []

    # === Cover ===
    story.append(Paragraph("Sample Lead Pack", h1))
    story.append(Paragraph(
        f"<b>Niche:</b> {_safe(niche_label)}", body))
    story.append(Paragraph(
        f"<b>Sample size:</b> {len(rows)} pre-qualified domains", body))
    story.append(Paragraph(
        f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d')} "
        f"by Idincode Apex Market Intelligence", small))
    story.append(Spacer(1, 10))

    story.append(Paragraph("What's in this pack", h2))
    story.append(Paragraph(
        "Each row below is a real business website that has been scored for "
        "marketing-infrastructure gaps (slow mobile speed, missing tracking "
        "pixels, no analytics, etc). These are the kind of prospects a "
        "performance marketing agency would target — ready to pitch, with "
        "the &quot;why now&quot; already proven from public website signals.",
        body,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "All data is observed from publicly accessible HTML. Owner emails "
        "(when shown) were scraped from the website itself or verified via MX "
        "lookup — no guessing.", small,
    ))
    story.append(Spacer(1, 10))

    # === Summary table ===
    story.append(Paragraph("Sample Overview", h2))
    table_rows = [["#", "Domain", "Score", "Primary Issue"]]
    for i, r in enumerate(rows, start=1):
        table_rows.append([
            str(i),
            _safe(r.get("domain", ""))[:42],
            f"{_safe_float(r.get('gold_score')):.2f}",
            _safe(_primary_issue(r))[:48],
        ])
    t = Table(
        table_rows,
        colWidths=[10 * mm, 70 * mm, 18 * mm, 72 * mm],
        repeatRows=1,
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde2e7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f6f8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)

    story.append(PageBreak())

    # === Per-lead detail ===
    for i, r in enumerate(rows, start=1):
        story.append(Paragraph(f"#{i} — {_safe(r.get('domain', ''))}", h2))

        ps = r.get("pagespeed_mobile", "") or "—"
        lcp = r.get("lcp_ms", "")
        lcp_str = f"{lcp} ms" if lcp else "—"
        detail = [
            ["Niche", _safe(r.get("niche", "") or "—")],
            ["Location", _safe(r.get("location", "") or "—")],
            ["Opportunity score",
             f"{_safe_float(r.get('gold_score')):.4f} / 1.00"],
            ["PageSpeed (mobile)", _safe(str(ps))],
            ["LCP", lcp_str],
            ["Meta Pixel",
             "Present" if not _is_no(r.get("meta_pixel_in_html")) else "Missing (gap)"],
            ["GA4",
             "Present" if not _is_no(r.get("ga4_in_html")) else "Missing (gap)"],
            ["Google Ads tag",
             "Present" if not _is_no(r.get("google_ads_in_html")) else "Missing (gap)"],
            ["Platform", _safe(r.get("platform", "") or "Unknown")],
            ["Primary issue", _safe(_primary_issue(r))],
            ["Owner email (scraped)",
             _safe(_first_email(r) or "—")],
            ["MX status", _mx_status(r)],
        ]
        story.append(_kv_table(detail))

        angle = (r.get("outreach_angle") or "").strip()
        if angle:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<b>Suggested outreach angle:</b> {_safe(angle)}", body))

        story.append(Spacer(1, 8))

    # Footer
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "This sample pack contains 100% public-source signals. Operators "
        "use this data to prioritize outreach — they are not ranked customer "
        "records. © Idincode Apex Market Intelligence.",
        small,
    ))

    doc.build(story)


def _kv_table(rows: list[list[str]]):
    t = Table(rows, colWidths=[55 * mm, 115 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f6f8")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0f4c81")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde2e7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


# ============================================================
# Utils
# ============================================================
def _safe(s: Any) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _slug(s: str) -> str:
    import re
    out = re.sub(r"[^a-zA-Z0-9._-]+", "_", (s or "").strip()).strip("_")
    return out.lower() or "pack"
