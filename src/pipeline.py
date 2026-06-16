# src/pipeline.py
"""Main orchestrator: load -> enrich -> extras -> qualify -> analyst -> export -> pdf.

Return summary dict yang dipakai run.py.
BI enrichment sekarang tier-aware & marketplace-detecting.
Export UTAMA: Google Sheets (rapi, shareable) + fallback CSV.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from src.analyst import enrich_with_ai_analyst
from src.bi_enrich import enrich_business_intelligence
from src.crm_webhooks import push_leads_to_crm
from src.dedup_db import DedupDB
from src.enrichers import enrich_all
from src.export import export_tiered_csvs
from src.export_sheets import export_to_sheets
from src.extras import enrich_extras_batch
from src.loader import load_targets
from src.pdf_audit import generate_pdf_audits
from src.qualifier import qualify_lead
from src.sheets_push import push_csvs_to_sheets


async def run_pipeline(
    targets_path: str = "targets.yaml",
    *,
    enable_extras: bool = True,
    enable_ads: bool = False,
    enable_competitors: bool = False,
    enable_bi: bool = True,
    enable_pdf: bool = True,
    pdf_min_score: float = 0.85,
    pdf_top_n: int = 25,
    enable_dedup: bool = True,
    include_seen: bool = False,
    reset_dedup: bool = False,
    enable_crm: bool = False,
    crm_min_score: float = 0.70,
    crm_limit: int = 0,
    crm_dry_run: bool = False,
    enable_email_verify: bool = False,
    email_verify_use_providers: bool = True,
    enable_sheets_export: bool = True,
    enable_sheets_push: bool = False,
    sheets_spreadsheet_id: str = "",
    sheets_spreadsheet_name: str = "",
) -> dict[str, Any]:
    """Run full pipeline. Return summary dict untuk reporting di run.py.
    
    Tier-aware BI enrichment: tier 1 brands diperlakukan sebagai established,
    marketplace signals di-deteksi untuk confidence boost.
    Export UTAMA sekarang Google Sheets (rapi, shareable).
    """
    start_ts = time.perf_counter()

    print("=" * 60)
    print("Apex Market Intelligence | By Idincode")
    print("=" * 60)

    db: DedupDB | None = None
    if enable_dedup:
        db = DedupDB()
        if reset_dedup:
            import os

            try:
                os.remove(db.path)
                print(f"[dedup] wiped {db.path}")
            except OSError:
                pass
            db = DedupDB()
        stats = db.stats()
        print(
            f"[dedup] enabled (db={stats['db_path']}, leads_seen={stats['leads_seen']}, "
            f"include_seen={include_seen})"
        )
    else:
        print("[dedup] DISABLED")

    targets = load_targets(targets_path)
    total_targets = len(targets)
    print(f"[pipeline] Loaded {total_targets} targets from {targets_path}")

    if db and not include_seen:
        before = len(targets)
        targets = [t for t in targets if not db.is_lead_seen(getattr(t, "domain", ""))]
        skipped = before - len(targets)
        if skipped:
            print(
                f"[dedup] skip {skipped} target yg udah pernah ke-process "
                f"(--include-seen kalau mau ulang)"
            )
        if not targets:
            print(
                "[dedup] semua target udah pernah ke-process. "
                "Tambah target baru atau pakai --include-seen."
            )
            duration = round(time.perf_counter() - start_ts, 2)
            return {
                "total_targets": total_targets,
                "reachable": 0,
                "qualified": 0,
                "output_files": [],
                "sheets_url": None,
                "pdf_files": [],
                "duration_seconds": duration,
            }

    normalized_targets: list[dict[str, Any]] = []
    for target in targets:
        if hasattr(target, "to_dict"):
            normalized_targets.append(target.to_dict())
            continue

        if isinstance(target, dict):
            normalized_targets.append(
                {
                    "domain": target.get("domain", ""),
                    "location": target.get("location"),
                    "niche": target.get("niche", "default"),
                    "category": target.get("category"),
                    "brand": target.get("brand"),
                    "tier": target.get("tier"),
                    "notes": target.get("notes"),
                }
            )
            continue

        normalized_targets.append(
            {
                "domain": getattr(target, "domain", ""),
                "location": getattr(target, "location", None),
                "niche": getattr(target, "niche", "default"),
                "category": getattr(target, "category", None),
                "brand": getattr(target, "brand", None),
                "tier": getattr(target, "tier", None),
                "notes": getattr(target, "notes", None),
            }
        )

    enrichments = await enrich_all(normalized_targets)

    reachable = [e for e in enrichments if getattr(e, "reachable", True)]
    unreachable = [e for e in enrichments if not getattr(e, "reachable", True)]

    if unreachable:
        print(f"\n[pipeline] WARN: {len(unreachable)} domains unreachable:")
        reasons: dict[str, int] = {}
        for enrichment in unreachable:
            reason = getattr(enrichment, "fail_reason", None) or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"   - {reason}: {count}")

    if not reachable:
        print("\n[pipeline] FATAL: 0 reachable domains.")
        output_files: list[str] = []
        sheets_url: str | None = None
        try:
            output_files = export_tiered_csvs([])
        except Exception as e:  # noqa: BLE001
            print(f"[pipeline] export empty failed: {e}")

        duration = round(time.perf_counter() - start_ts, 2)
        return {
            "total_targets": total_targets,
            "reachable": 0,
            "qualified": 0,
            "output_files": output_files,
            "sheets_url": sheets_url,
            "pdf_files": [],
            "duration_seconds": duration,
        }

    # ============================================================
    # BUSINESS INTELLIGENCE ENRICHMENT (tier-aware, marketplace-aware)
    # ============================================================
    if enable_bi:
        print(f"\n[pipeline] BI enrichment (tier-aware) untuk {len(reachable)} leads...")
        for enrichment in reachable:
            raw_html = getattr(enrichment, "raw_html", "") or ""
            domain = getattr(enrichment, "domain", "")
            tier = getattr(enrichment, "tier", None)
            brand = getattr(enrichment, "brand", None)

            bi_data = enrich_business_intelligence(
                html=raw_html,
                domain=domain,
                tier=tier,
                brand=brand,
            )

            # Copy all BI fields ke enrichment
            setattr(enrichment, "employee_range", bi_data.get("employee_range", "unknown"))
            setattr(enrichment, "location_count", bi_data.get("location_count", 0))
            setattr(enrichment, "founded_year", bi_data.get("founded_year"))
            setattr(enrichment, "years_in_business", bi_data.get("years_in_business"))
            setattr(enrichment, "social_profiles", bi_data.get("social_profiles", []))
            setattr(enrichment, "tech_signals", bi_data.get("tech_signals", []))
            setattr(enrichment, "marketplaces", bi_data.get("marketplaces", []))
            setattr(enrichment, "bi_score", bi_data.get("bi_score", 0))
            setattr(enrichment, "firmographics_confidence", bi_data.get("firmographics_confidence", "low"))
            setattr(enrichment, "firmographics_source", bi_data.get("firmographics_source", "free_enrichment"))
            setattr(enrichment, "detection_notes", bi_data.get("detection_notes", ""))

            # Merge data_quality_flags dari pixel detection + bi enrich
            existing_flags = getattr(enrichment, "data_quality_flags", []) or []
            bi_flags = bi_data.get("data_quality_flags", [])
            merged_flags = list(set(existing_flags + bi_flags))
            setattr(enrichment, "data_quality_flags", merged_flags)

    # ============================================================
    # EXTRAS ENRICHMENT (emails, revenue, ads, competitors, etc)
    # ============================================================
    if enable_extras:
        print(f"\n[pipeline] Extras enrichment untuk {len(reachable)} leads...")
        base_htmls = {
            getattr(enrichment, "domain", ""): getattr(enrichment, "raw_html", "") or ""
            for enrichment in reachable
        }
        extras_results = await enrich_extras_batch(
            reachable,
            base_htmls=base_htmls,
            enable_emails=True,
            enable_revenue=True,
            enable_ads=enable_ads,
            enable_competitors=enable_competitors,
            enable_bi=False,  # BI sudah dikerjain di atas, jangan ulang
            enable_email_verify=enable_email_verify,
            email_verify_use_providers=email_verify_use_providers,
        )
        for enrichment, extra in zip(reachable, extras_results):
            for key, value in extra.items():
                setattr(enrichment, key, value)

    print(f"\n[pipeline] Scoring {len(reachable)} reachable leads...")
    qualified = [qualify_lead(enrichment) for enrichment in reachable]

    qualified = await enrich_with_ai_analyst(qualified)

    qualified.sort(key=lambda x: x.score, reverse=True)

    # ============================================================
    # EXPORT: PRIMARY = GOOGLE SHEETS (RAPI), FALLBACK = CSV
    # ============================================================
    output_files: list[str] = []
    sheets_url: str | None = None

    if enable_sheets_export:
        print(f"\n[pipeline] Exporting to Google Sheets (rapi, shareable)...")
        try:
            sheets_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            sheets_name = sheets_spreadsheet_name or f"Idincode Research — {sheets_timestamp}"

            sheets_result = export_to_sheets(
                qualified,
                spreadsheet_id=sheets_spreadsheet_id or "",
                spreadsheet_name=sheets_name,
            )

            sheets_url = sheets_result.get("spreadsheet_url")
            sheets_id = sheets_result.get("spreadsheet_id")
            sheets_created = sheets_result.get("sheets_created", [])

            print(f"[sheets] ✅ Spreadsheet created/updated: {sheets_id}")
            print(f"[sheets] 📊 Sheets: {', '.join(sheets_created)}")
            print(f"[sheets] 🔗 URL: {sheets_url}")

            output_files.append(sheets_url)

        except Exception as e:  # noqa: BLE001
            print(f"[sheets] ❌ FALLBACK to CSV (reason: {type(e).__name__}: {str(e)[:100]})")
            try:
                output_files = export_tiered_csvs(qualified)
            except Exception as e2:  # noqa: BLE001
                print(f"[export] CSV export juga gagal: {e2}")
                output_files = []
    else:
        # CSV export (backward compatible)
        print(f"\n[pipeline] Exporting to CSV (legacy)...")
        try:
            output_files = export_tiered_csvs(qualified)
        except Exception as e:  # noqa: BLE001
            print(f"[export] CSV export failed: {e}")
            output_files = []

    # ============================================================
    # PDF AUDIT GENERATION
    # ============================================================
    pdf_files: list[str] = []
    if enable_pdf:
        print(f"\n[pipeline] Generating PDF audits (top {pdf_top_n}, min score {pdf_min_score})...")
        try:
            pdf_files = generate_pdf_audits(
                qualified,
                output_dir="output/pdf",
                only_top=pdf_top_n,
                min_score=pdf_min_score,
            )
            print(f"[pdf] ✅ Generated {len(pdf_files)} audit PDFs")
        except Exception as e:  # noqa: BLE001
            print(f"[pdf] WARN: PDF generation failed: {e}")
            pdf_files = []

    # ============================================================
    # CRM WEBHOOK PUSH (OPTIONAL)
    # ============================================================
    crm_summary: dict[str, Any] | None = None
    if enable_crm:
        print(
            f"\n[pipeline] CRM push (min_score={crm_min_score}, "
            f"limit={crm_limit or 'all'}, dry_run={crm_dry_run})..."
        )
        try:
            crm_summary = await push_leads_to_crm(
                qualified,
                min_score=crm_min_score,
                limit=crm_limit,
                dry_run=crm_dry_run,
            )
            print(f"[crm] ✅ Push successful: {crm_summary}")
        except Exception as e:  # noqa: BLE001
            print(f"[crm] ❌ Push failed: {type(e).__name__}: {e}")
            crm_summary = {"error": f"{type(e).__name__}: {e}"}

    # ============================================================
    # GOOGLE SHEETS PUSH (PUSH CSV BACKUP TO EXISTING SHEET)
    # ============================================================
    sheets_push_summary: dict[str, Any] | None = None
    if enable_sheets_push and output_files:
        print("\n[pipeline] Pushing CSV backup to existing Google Sheet...")
        try:
            sheets_push_summary = push_csvs_to_sheets(
                output_files,
                spreadsheet_id=sheets_spreadsheet_id or None,
                spreadsheet_name=sheets_spreadsheet_name or None,
            )
            print(f"[sheets_push] ✅ Pushed: {sheets_push_summary}")
        except Exception as e:  # noqa: BLE001
            print(f"[sheets_push] WARN: Push failed: {type(e).__name__}: {e}")
            sheets_push_summary = {"error": f"{type(e).__name__}: {e}"}

    # ============================================================
    # DEDUP PERSISTENCE
    # ============================================================
    if db:
        for enrichment in reachable:
            domain = getattr(enrichment, "domain", "")
            if domain:
                db.mark_lead(domain)
        stats = db.stats()
        print(f"\n[dedup] ✅ Persisted. Total leads_seen={stats['leads_seen']}")

    # ============================================================
    # SUMMARY & TIMING
    # ============================================================
    duration = round(time.perf_counter() - start_ts, 2)

    print("\n" + "=" * 60)
    print("Pipeline Complete! ✅")
    print("=" * 60)
    if sheets_url:
        print(f"📊 Google Sheets: {sheets_url}")
    if pdf_files:
        print(f"📄 PDF Audits: {len(pdf_files)} files generated")
    print(f"⏱️  Total time: {duration}s")
    print("=" * 60)

    return {
        "total_targets": total_targets,
        "reachable": len(reachable),
        "qualified": len(qualified),
        "output_files": output_files,
        "sheets_url": sheets_url,
        "pdf_files": pdf_files,
        "crm": crm_summary,
        "sheets_push": sheets_push_summary,
        "duration_seconds": duration,
    }


def main() -> None:
    """Main entry point untuk CLI."""
    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()
