from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Load .env kalau ada (graceful, gak crash kalau gak ada)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.business_pipeline import BusinessIntelPipeline, BusinessPipelineConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run business-intelligence research for target brands."
    )
    parser.add_argument("--targets", default="targets.yaml")
    parser.add_argument("--output-dir", default="artifacts/business_intel")
    parser.add_argument("--enable-sheets-export", action="store_true")
    parser.add_argument("--disable-sheets-export", action="store_true")
    parser.add_argument("--sheets-id", default=os.getenv("GSHEET_SPREADSHEET_ID", ""))
    parser.add_argument("--sheet-title", default="IdinCode Business Intelligence")
    parser.add_argument("--max-concurrency", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    return parser


async def async_main() -> int:
    args = build_parser().parse_args()
    targets_path = Path(args.targets)
    output_dir = Path(args.output_dir)

    if not targets_path.exists():
        print(f"❌ ERROR: targets file not found: {targets_path}", file=sys.stderr)
        print(f"   Current working dir: {Path.cwd()}", file=sys.stderr)
        return 1

    enable_sheets_export = args.enable_sheets_export and not args.disable_sheets_export

    config = BusinessPipelineConfig(
        targets_path=targets_path,
        output_dir=output_dir,
        max_concurrency=args.max_concurrency,
        timeout_seconds=args.timeout_seconds,
        user_agent=args.user_agent,
        enable_sheets_export=enable_sheets_export,
        sheets_id=args.sheets_id.strip() or None,
        sheet_title=args.sheet_title.strip(),
    )

    print(f"🚀 Starting Business Intelligence Pipeline")
    print(f"   Targets file: {targets_path}")
    print(f"   Output dir:   {output_dir}")
    print(f"   Sheets export: {enable_sheets_export}")
    print()

    pipeline = BusinessIntelPipeline(config)
    try:
        await pipeline.run()
    except Exception as exc:
        print(f"❌ Pipeline failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
