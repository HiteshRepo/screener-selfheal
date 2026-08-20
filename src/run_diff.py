#!/usr/bin/env python3
"""CLI entry point: diff the latest scrape snapshot against the previous one."""

import argparse
import logging
import sys

from diff_engine import DiffEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff latest scrape snapshot against previous.")
    parser.add_argument(
        "--data-dir",
        default="data/production",
        help="Directory containing latest.json and previous.json (default: data/production).",
    )
    args = parser.parse_args()

    engine = DiffEngine()

    latest, previous = engine.load_snapshots(
        latest_path=f"{args.data_dir}/latest.json",
        previous_path=f"{args.data_dir}/previous.json",
    )

    result = engine.diff(latest, previous)
    report_path = engine.write_report(result, output_dir=args.data_dir)

    print(
        f"Diff complete: {len(result.entered)} entered, {len(result.exited)} exited, "
        f"{len(result.changed)} changed, {len(result.unchanged)} unchanged "
        f"→ {report_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
