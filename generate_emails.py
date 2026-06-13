"""Generate AI-personalized cold emails from latest leads/buyers CSV.

Built by Idin Iskandar.

Run setelah `run.py` (leads) atau `find_buyer.py` (buyers).
Membaca CSV terbaru, generate email (subject + body + CTA) lewat AI macro
(kie.ai / Claude) yang sama dengan analyst layer, lalu tulis hasilnya ke:

    output/emails/leads/<domain>.md       (1 file per lead)
    output/emails/buyers/<domain>__<email>.md
    output/emails/emails_index.csv        (summary semua subject)

Usage:
    python generate_emails.py                       # auto: leads + buyers
    python generate_emails.py --source leads        # leads only
    python generate_emails.py --source buyers       # buyers only
    python generate_emails.py --limit 20            # cap jumlah email
    python generate_emails.py --leads-csv path.csv  # override input file
    python generate_emails.py --buyers-csv path.csv
    python generate_emails.py --out output/emails   # output dir

Tanpa IDINCODE_API → tetap jalan pakai template fallback (warning printed).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.config import IDINCODE_API
from src.email_generator import (
    generate_emails_for_agency_pitch,
    generate_emails_for_buyers,
    generate_emails_for_leads,
)


# ============================================================
# Lightweight rehydrators: read CSV -> objects yang email_generator
# bisa konsumsi (cuma butuh attribute access).
# ============================================================
@dataclass
class _LeadRow:
    domain: str
    niche: str = ""
    location: str = ""
    score: float = 0.0
    pagespeed_score: Optional[int] = None
    lcp_ms: Optional[int] = None
    meta_pixel_in_html: bool = False
    ga4_in_html: bool = False
    google_ads_in_html: bool = False


@dataclass
class _BuyerPerson:
    name: str
    title: str
    email: str


@dataclass
class _BuyerLead:
    agency_domain: str
    agency_name: str
    niche_keyword: str
    country: str
    persons: list[_BuyerPerson]


# ============================================================
# CSV readers
# ============================================================
def _safe_int(v: str) -> Optional[int]:
    try:
        return int(float(v)) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def _safe_float(v: str) -> float:
    try:
        return float(v) if v not in ("", None) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _bool_csv(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _find_latest(dir_path: str, prefix: str) -> Optional[str]:
    p = Path(dir_path)
    if not p.exists():
        return None
    candidates = sorted(p.glob(f"{prefix}*.csv"), reverse=True)
    return str(candidates[0]) if candidates else None


def read_leads_csv(path: str, *, limit: Optional[int]) -> list[_LeadRow]:
    rows: list[_LeadRow] = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(_LeadRow(
                domain=r.get("domain", "").strip(),
                niche=r.get("niche", "") or "",
                location=r.get("location", "") or "",
                score=_safe_float(r.get("gold_score", "0")),
                pagespeed_score=_safe_int(r.get("pagespeed_mobile", "")),
                lcp_ms=_safe_int(r.get("lcp_ms", "")),
                meta_pixel_in_html=_bool_csv(r.get("meta_pixel_in_html", "")),
                ga4_in_html=_bool_csv(r.get("ga4_in_html", "")),
                google_ads_in_html=_bool_csv(r.get("google_ads_in_html", "")),
            ))
            if limit and len(rows) >= limit:
                break
    return [r for r in rows if r.domain]


def read_buyers_csv(path: str, *, limit: Optional[int]) -> list[_BuyerLead]:
    by_agency: dict[str, _BuyerLead] = {}
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            domain = r.get("agency_domain", "").strip()
            email = r.get("email", "").strip()
            if not domain or not email:
                continue
            if domain not in by_agency:
                by_agency[domain] = _BuyerLead(
                    agency_domain=domain,
                    agency_name=r.get("agency_name", domain),
                    niche_keyword=r.get("niche_keyword", ""),
                    country=r.get("country", "US"),
                    persons=[],
                )
            by_agency[domain].persons.append(_BuyerPerson(
                name=r.get("person_name", "").strip(),
                title=r.get("person_title", "").strip(),
                email=email,
            ))
            count += 1
            if limit and count >= limit:
                break
    return list(by_agency.values())


def read_agency_buyers_csv(path: str, *, limit: Optional[int]) -> list[_BuyerLead]:
    """Reader untuk output find_agency_buyers.py (agency_buyers_latest.csv).

    Beda kolom sama buyers CSV: pakai website/ceo_name/ceo_title/niche_keyword.
    """
    by_agency: dict[str, _BuyerLead] = {}
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            website = (r.get("website") or "").strip()
            email = (r.get("email") or "").strip()
            if not website or not email:
                continue
            # normalize "https://www.foo.com/..." -> "foo.com"
            domain = re.sub(r"^https?://", "", website, flags=re.I)
            domain = domain.split("/", 1)[0]
            domain = re.sub(r"^www\.", "", domain, flags=re.I).lower()
            if domain not in by_agency:
                by_agency[domain] = _BuyerLead(
                    agency_domain=domain,
                    agency_name=(r.get("agency_name") or domain).strip() or domain,
                    niche_keyword=(r.get("niche_keyword") or "").strip(),
                    country=(r.get("country") or "US").strip() or "US",
                    persons=[],
                )
            by_agency[domain].persons.append(_BuyerPerson(
                name=(r.get("ceo_name") or "").strip(),
                title=(r.get("ceo_title") or "Owner").strip() or "Owner",
                email=email,
            ))
            count += 1
            if limit and count >= limit:
                break
    return list(by_agency.values())


def _load_latest_sample_summary() -> Optional[dict]:
    """Coba detect sample pack terbaru dari output/sample_pack/."""
    p = Path("output/sample_pack")
    if not p.exists():
        return None
    csvs = sorted(p.glob("*_sample_*.csv"), reverse=True)
    if not csvs:
        return None
    latest_csv = csvs[0]
    # niche dari prefix nama file
    name = latest_csv.stem  # e.g. "plastic_surgery_sample_20260101_120000"
    niche = name.split("_sample_")[0].replace("_", " ")
    # hitung row
    try:
        with latest_csv.open("r", encoding="utf-8") as f:
            count = sum(1 for _ in csv.DictReader(f))
    except OSError:
        count = 0
    pdf_path = latest_csv.with_suffix(".pdf")
    return {
        "niche": niche,
        "count": count,
        "csv_file": str(latest_csv),
        "pdf_file": str(pdf_path) if pdf_path.exists() else None,
    }




# ============================================================
# Writers
# ============================================================
def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s).strip("_") or "x"


def _write_md(path: str, *, subject: str, body: str, cta: str, meta: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append(f"subject: {subject}")
    lines.append("---")
    lines.append("")
    lines.append(f"**Subject:** {subject}")
    lines.append("")
    lines.append(body)
    if cta:
        lines.append("")
        lines.append(f"_{cta}_")
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _append_index(index_path: str, row: dict) -> None:
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    is_new = not os.path.exists(index_path)
    fields = ["source", "domain", "email", "subject", "cta", "file"]
    with open(index_path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


# ============================================================
# Drivers
# ============================================================
async def _do_leads(csv_path: str, out_dir: str, limit: Optional[int]) -> int:
    print(f"[gen-emails] Leads source: {csv_path}")
    rows = read_leads_csv(csv_path, limit=limit)
    if not rows:
        print("[gen-emails] WARN: no rows in leads CSV.")
        return 0
    out = await generate_emails_for_leads(rows)
    idx = os.path.join(out_dir, "emails_index.csv")
    written = 0
    for r in rows:
        e = out.get(r.domain)
        if not e:
            continue
        path = os.path.join(out_dir, "leads", f"{_slug(r.domain)}.md")
        _write_md(
            path,
            subject=e["subject"], body=e["body"], cta=e["cta"],
            meta={
                "source": "leads",
                "domain": r.domain,
                "niche": r.niche,
                "score": r.score,
            },
        )
        _append_index(idx, {
            "source": "leads", "domain": r.domain, "email": "",
            "subject": e["subject"], "cta": e["cta"], "file": path,
        })
        written += 1
    print(f"[gen-emails] Wrote {written} lead emails -> {out_dir}/leads/")
    return written


async def _do_buyers(csv_path: str, out_dir: str, limit: Optional[int]) -> int:
    print(f"[gen-emails] Buyers source: {csv_path}")
    leads = read_buyers_csv(csv_path, limit=limit)
    if not leads:
        print("[gen-emails] WARN: no rows in buyers CSV.")
        return 0
    out = await generate_emails_for_buyers(leads)
    idx = os.path.join(out_dir, "emails_index.csv")
    written = 0
    for l in leads:
        for p in l.persons:
            key = f"{l.agency_domain}|{p.email.lower()}"
            e = out.get(key)
            if not e:
                continue
            fname = f"{_slug(l.agency_domain)}__{_slug(p.email)}.md"
            path = os.path.join(out_dir, "buyers", fname)
            _write_md(
                path,
                subject=e["subject"], body=e["body"], cta=e["cta"],
                meta={
                    "source": "buyers",
                    "agency_domain": l.agency_domain,
                    "agency_name": l.agency_name,
                    "niche": l.niche_keyword,
                    "person": p.name,
                    "title": p.title,
                    "email": p.email,
                },
            )
            _append_index(idx, {
                "source": "buyers", "domain": l.agency_domain,
                "email": p.email, "subject": e["subject"],
                "cta": e["cta"], "file": path,
            })
            written += 1
    print(f"[gen-emails] Wrote {written} buyer emails -> {out_dir}/buyers/")
    return written


async def _do_agency_pitch(
    csv_path: str,
    out_dir: str,
    limit: Optional[int],
    sample_summary: Optional[dict],
) -> int:
    print(f"[gen-emails] Agency-pitch source: {csv_path}")
    leads = read_agency_buyers_csv(csv_path, limit=limit)
    if not leads:
        print("[gen-emails] WARN: no rows in agency_buyers CSV.")
        return 0
    if sample_summary:
        print(
            f"[gen-emails] Sample pack context: "
            f"niche={sample_summary.get('niche')} | "
            f"count={sample_summary.get('count')} | "
            f"csv={sample_summary.get('csv_file')}"
        )
    else:
        print("[gen-emails] No sample pack found — pitch will be generic. "
              "Jalanin `python make_sample_pack.py` dulu utk hasil terbaik.")
    out = await generate_emails_for_agency_pitch(
        leads, sample_summary=sample_summary
    )
    idx = os.path.join(out_dir, "emails_index.csv")
    written = 0
    for l in leads:
        for p in l.persons:
            key = f"{l.agency_domain}|{p.email.lower()}"
            e = out.get(key)
            if not e:
                continue
            fname = f"{_slug(l.agency_domain)}__{_slug(p.email)}.md"
            path = os.path.join(out_dir, "agency_pitch", fname)
            meta = {
                "source": "agency_pitch",
                "agency_domain": l.agency_domain,
                "agency_name": l.agency_name,
                "niche": l.niche_keyword,
                "person": p.name,
                "title": p.title,
                "email": p.email,
            }
            if sample_summary:
                if sample_summary.get("csv_file"):
                    meta["attach_csv"] = sample_summary["csv_file"]
                if sample_summary.get("pdf_file"):
                    meta["attach_pdf"] = sample_summary["pdf_file"]
            _write_md(
                path,
                subject=e["subject"], body=e["body"], cta=e["cta"],
                meta=meta,
            )
            _append_index(idx, {
                "source": "agency_pitch", "domain": l.agency_domain,
                "email": p.email, "subject": e["subject"],
                "cta": e["cta"], "file": path,
            })
            written += 1
    print(f"[gen-emails] Wrote {written} agency-pitch emails -> {out_dir}/agency_pitch/")
    return written


# ============================================================
# CLI
# ============================================================
def _banner() -> None:
    print("=" * 64)
    print("  APEX EMAIL GENERATOR — Personalized Cold Email (AI)")
    print("  Built by Idin Iskandar")
    print("=" * 64)


async def _main(args: argparse.Namespace) -> int:
    _banner()
    print(f"[ENV] IDINCODE_API: {'SET' if IDINCODE_API else 'MISSING (fallback template)'}")
    out_dir = args.out

    total = 0
    if args.source in ("leads", "both"):
        path = args.leads_csv or _find_latest("output", "leads_premium_gold") \
            or _find_latest("output", "leads_pro") \
            or _find_latest("output", "leads_starter")
        if not path:
            print("[gen-emails] No leads CSV found (jalanin `python run.py` dulu).")
        else:
            total += await _do_leads(path, out_dir, args.limit)

    if args.source in ("buyers", "both"):
        path = args.buyers_csv or _find_latest("output/buyers", "buyers_latest") \
            or _find_latest("output/buyers", "buyers_")
        if not path:
            print("[gen-emails] No buyers CSV found (jalanin `python find_buyer.py` dulu).")
        else:
            total += await _do_buyers(path, out_dir, args.limit)

    if args.source == "agency-pitch":
        path = args.agency_csv \
            or _find_latest("output/agency_buyers", "agency_buyers_latest") \
            or _find_latest("output/agency_buyers", "agency_buyers_")
        if not path:
            print("[gen-emails] No agency_buyers CSV found "
                  "(jalanin `python find_agency_buyers.py` dulu).")
        else:
            sample = None if args.no_sample_context else _load_latest_sample_summary()
            total += await _do_agency_pitch(path, out_dir, args.limit, sample)

    print("=" * 64)
    print(f"  DONE — {total} emails generated")
    print(f"  Output dir : {out_dir}/")
    print(f"  Index CSV  : {out_dir}/emails_index.csv")
    print("=" * 64)
    return 0 if total > 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate AI-personalized cold emails from leads/buyers/agency CSV"
    )
    parser.add_argument(
        "--source",
        choices=("leads", "buyers", "both", "agency-pitch"),
        default="both",
        help="Which pipeline output to use. 'agency-pitch' = pitch sample "
             "lead pack ke agency luar (US/UK/AU/EU).",
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap jumlah email yang di-generate")
    parser.add_argument("--leads-csv", default=None,
                        help="Path manual ke leads CSV (override auto-detect)")
    parser.add_argument("--buyers-csv", default=None,
                        help="Path manual ke buyers CSV (override auto-detect)")
    parser.add_argument("--agency-csv", default=None,
                        help="Path manual ke agency_buyers CSV (override auto-detect)")
    parser.add_argument("--no-sample-context", action="store_true",
                        help="Skip auto-detect sample pack (untuk agency-pitch)")
    parser.add_argument("--out", default="output/emails",
                        help="Output directory")
    args = parser.parse_args()

    try:
        code = asyncio.run(_main(args))
    except KeyboardInterrupt:
        print("\n[ABORTED] User interrupted.", file=sys.stderr)
        code = 130
    sys.exit(code)



if __name__ == "__main__":
    main()
