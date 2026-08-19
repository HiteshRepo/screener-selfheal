"""Test Bright Data's automate_template API locally.

Sends a Stage 2 prompt to Bright Data's AI, polls for progress,
and prints the generated code — WITHOUT approving/saving it.

Usage:
    make automate-stage2
"""

import os
import sys
import time

import requests

_BASE_URL = "https://api.brightdata.com"
_POLL_INTERVAL = 5
_TIMEOUT = 300

# Sample company page URLs — Bright Data's AI visits these to infer the page structure
_SAMPLE_URLS = [
    "https://www.screener.in/company/INFY/consolidated/",
    "https://www.screener.in/company/GULFOILLUB/",
]


def main() -> int:
    token = os.environ.get("BRIGHT_DATA_API_TOKEN")
    collector_id = os.environ.get("BRIGHT_DATA_COLLECTOR_ID")

    if not token:
        print("ERROR: BRIGHT_DATA_API_TOKEN not set.", file=sys.stderr)
        return 1
    if not collector_id:
        print("ERROR: BRIGHT_DATA_COLLECTOR_ID not set.", file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"

    print(f"Collector : {collector_id}")
    print(f"URLs      : {_SAMPLE_URLS}")
    print()

    # Trigger automate_template
    resp = session.post(
        f"{_BASE_URL}/dca/collectors/{collector_id}/automate_template",
        json={"urls": _SAMPLE_URLS},
    )
    print(f"Trigger status : {resp.status_code}")
    if not resp.ok:
        print(f"ERROR: {resp.text}")
        return 1

    data = resp.json()
    job_id = data.get("job_id") or data.get("id") or ""
    print(f"Job ID         : {job_id}")
    print()

    # Poll progress
    start = time.monotonic()
    poll_url = f"{_BASE_URL}/dca/collectors/{collector_id}/automate_template/progress"
    _TERMINAL = {"done", "pending_answer"}

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= _TIMEOUT:
            print(f"ERROR: Timed out after {elapsed:.0f}s")
            return 1

        resp = session.get(poll_url)
        if not resp.ok:
            print(f"Poll error {resp.status_code}: {resp.text}")
            return 1

        result = resp.json()
        status = result.get("status", "")
        print(f"[{elapsed:5.0f}s] status={status}")

        if status in _TERMINAL:
            print()
            print("=" * 60)
            print("GENERATED OUTPUT (NOT saved — review before approving)")
            print("=" * 60)

            # Print all fields returned
            for k, v in result.items():
                if k == "status":
                    continue
                if isinstance(v, str) and len(v) > 200:
                    print(f"\n--- {k} ---")
                    print(v)
                else:
                    print(f"{k}: {v}")

            print()
            print("To approve and save: implement approve step (resume_automation_job)")
            print("To reject:           do nothing — changes are NOT saved yet")
            return 0

        time.sleep(_POLL_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
