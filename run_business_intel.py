from __future__ import annotations

import argparse
import asyncio
import os
import sys
import traceback
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.business_pipeline import BusinessIntelPipeline, BusinessPipelineConfig


def build_parser():
    parser = argparse.ArgumentParser(description="Run business intelligence research.")
    parser.add_argument("--targets", default="targets.yaml")
    parser.add_argument("--output-dir", default="artifacts/business_intel")
    parser.add_argument("--max-concurrency", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument(
        "--user-agent",
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )
    return parser


async def async_main():
    args = build_parser().parse_args()
    targets_path = Path(args.targets)
    output_dir = Path(args.output_dir)

    if not targets_path.exists():
        print("ERROR: targets file not found: " + str(targets_path), file=sys.stderr)
        return 1

    config = BusinessPipelineConfig(
        targets_path=targets_path,
        output_dir=output_dir,
        max_concurrency=args.max_concurrency,
        timeout_seconds=args.timeout_seconds,
        user_agent=args.user_agent,
    )

    print("Starting Business Intelligence Pipeline")
    print("  Targets file: " + str(targets_path))
    print("  Output dir:   " + str(output_dir))
    print("")

    pipeline = BusinessIntelPipeline(config)
    try:
        await pipeline.run()
    except Exception as exc:
        print("Pipeline failed: " + str(exc), file=sys.stderr)
        traceback.print_exc()
        return 1
    return 0


def main():
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
