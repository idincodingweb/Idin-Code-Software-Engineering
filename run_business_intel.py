from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from src.business_pipeline import BusinessIntelPipeline, BusinessPipelineConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run business-intelligence research for target brands."
    )
    parser.add_argument(
        "--targets",
        default="targets.yaml",
        help="Path to targets YAML file.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/business_intel",
        help="Directory for CSV outputs.",
    )
    parser.add_argument(
        "--enable-sheets-export",
        action="store_true",
        help="Export results to Google Sheets.",
    )
    parser.add_argument(
        "--disable-sheets-export",
        action="store_true",
        help="Force-disable Google Sheets export even if env vars exist.",
    )
    parser.add_argument(
        "--sheets-id",
        default=os.getenv("GSHEET_SPREADSHEET_ID", ""),
        help="Existing spreadsheet ID to update. If empty, a new one may be created.",
    )
    parser.add_argument(
        "--sheet-title",
        default="IdinCode Business Intelligence",
        help="Spreadsheet title when creating a new Google Sheet.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=6,
        help="Maximum concurrent target fetches.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="HTTP timeout for website fetches.",
    )
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        help="User-Agent for website requests.",
    )
    return parser


async def async_main() -> int:
    args = build_parser().parse_args()
    targets_path = Path(args.targets)
    output_dir = Path(args.output_dir)

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
    pipeline = BusinessIntelPipeline(config)
    await pipeline.run()
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
