"""Validate data/latest.json: record count matches meta and all records pass schema."""

import json
import sys

sys.path.insert(0, "src")

from schema import validate_record  # noqa: E402


def main() -> int:
    with open("data/latest.json", encoding="utf-8") as fh:
        envelope = json.load(fh)

    records = envelope.get("records", [])
    meta = envelope.get("meta", {})

    assert meta.get("record_count") == len(records), (
        f"meta.record_count {meta['record_count']} != {len(records)}"
    )

    for r in records:
        validate_record(r)

    print(f"OK — {len(records)} record(s) validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
