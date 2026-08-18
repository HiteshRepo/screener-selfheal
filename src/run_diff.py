#!/usr/bin/env python3
"""CLI entry point: diff the latest scrape snapshot against the previous one."""

import logging
import sys

from diff_engine import DiffEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    engine = DiffEngine()

    latest, previous = engine.load_snapshots(
        latest_path="data/latest.json",
        previous_path="data/previous.json",
    )

    result = engine.diff(latest, previous)
    report_path = engine.write_report(result)

    print(
        f"Diff complete: {len(result.entered)} entered, {len(result.exited)} exited, "
        f"{len(result.changed)} changed, {len(result.unchanged)} unchanged "
        f"→ {report_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
