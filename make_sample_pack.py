"""make_sample_pack.py — generate "sample pack" buat dilampirin ke email outreach.

Built by Idin Iskandar.

Workflow:
    1. python run.py            # generate leads_all.csv & leads_premium_gold.csv
    2. python make_sample_pack.py --top 10
    3. Lampirin output/sample_pack/*.pdf & *.csv ke cold email agency

Usage:
    python make_sample_pack.py
    python make_sample_pack.py --top 5
    python make_sample_pack.py --niche plastic_surgery
    python make_sample_pack.py --input output/leads_premium_gold.csv
    python make_sample_pack.py --min-score 0.70
    python make_sample_pack.py --out output/sample_pack
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from src.sample_pack import build_sample_pack


def _find_latest_leads_csv() -> str | None:
    """Prefer premium gold -> pro -> starter -> leads_all."""
    candidates = [
        "output/leads_premium_gold.csv",
        "output/leads_pro.csv",
        "output/leads_starter.csv",
        "output/leads_all.csv",
    ]
    for c in candidates:
        if Path(c).exists() and Path(c).stat().st_size > 0:
            return c
    # Glob fallback (timestamped variants kalau ada)
    p = Path("output")
    if p.exists():
        for prefix in ("leads_premium_gold", "leads_pro", "leads_starter", "leads_all"):
            hits = sorted(p.glob(f"{prefix}*.csv"), reverse=True)
            if hits:
                return str(hits[0])
    return None


def _read_csv(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _banner() -> None:
    print("=" * 64)
    print("  APEX SAMPLE PACK GENERATOR — Lead Showcase for Agency Outreach")
    print("  Built by Idin Iskandar")
    print("=" * 64)


def main() -> int:
    _banner()
    parser = argparse.ArgumentParser(
        description="Build curated sample lead pack (CSV + PDF) for outreach"
    )
    parser.add_argument("--input", default=None,
                        help="Path to leads CSV (default: auto-detect)")
    parser.add_argument("--top", type=int, default=10,
                        help="Top-N leads to include (default 10)")
    parser.add_argument("--niche", default=None,
                        help="Filter by niche substring (e.g. 'plastic_surgery')")
    parser.add_argument("--min-score", type=float, default=0.50,
                        help="Minimum gold_score (default 0.50)")
    parser.add_argument("--out", default="output/sample_pack",
                        help="Output directory")
    args = parser.parse_args()

    src_path = args.input or _find_latest_leads_csv()
    if not src_path:
        print("[sample-pack] ERROR: no leads CSV found in output/. "
              "Jalanin `python run.py` dulu.", file=sys.stderr)
        return 1
    print(f"[sample-pack] Input  : {src_path}")
    print(f"[sample-pack] Top-N  : {args.top}")
    print(f"[sample-pack] Niche  : {args.niche or '(auto)'}")
    print(f"[sample-pack] MinScr : {args.min_score}")

    try:
        rows = _read_csv(src_path)
    except OSError as e:
        print(f"[sample-pack] ERROR reading CSV: {e}", file=sys.stderr)
        return 1

    if not rows:
        print("[sample-pack] ERROR: CSV is empty.", file=sys.stderr)
        return 1

    result = build_sample_pack(
        rows,
        niche_label=args.niche,
        out_dir=args.out,
        top_n=args.top,
        min_score=args.min_score,
    )

    print("=" * 64)
    print(f"  SAMPLE PACK READY — {result['count']} leads ({result['niche']})")
    if result.get("csv"):
        print(f"  CSV : {result['csv']}")
    if result.get("pdf"):
        print(f"  PDF : {result['pdf']}")
    else:
        print("  PDF : (skipped — install reportlab for PDF output)")
    print("=" * 64)
    return 0 if result["count"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
