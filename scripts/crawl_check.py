"""Quick diagnostic: call the Bright Data Crawl API and print the response structure.

Usage:
    CRAWL_URL=https://www.screener.in/company/GULFOILLUB/ make crawl-check
    make crawl-check  # uses default screen listing URL
"""

import os
import sys

import requests

_DATASET_ID = "gd_m6gjtfmeh43we6cqc"
_DEFAULT_URL = "https://www.screener.in/screens/3/highest-dividend-yield-shares/"


def main() -> int:
    token = os.environ.get("BRIGHT_DATA_API_TOKEN")
    if not token:
        print("ERROR: BRIGHT_DATA_API_TOKEN is not set.", file=sys.stderr)
        return 1

    url = os.environ.get("CRAWL_URL", _DEFAULT_URL)
    print(f"Fetching: {url}")

    resp = requests.post(
        "https://api.brightdata.com/datasets/v3/scrape",
        params={"dataset_id": _DATASET_ID, "notify": "false", "include_errors": "true"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"input": [{"url": url}], "limit_per_input": None},
        timeout=60,
    )

    print(f"HTTP status : {resp.status_code}")

    try:
        data = resp.json()
    except Exception as exc:
        print(f"Failed to parse JSON: {exc}")
        print(f"Raw response: {resp.text[:500]}")
        return 1

    if isinstance(data, dict):
        print(f"Response type: dict")
        print(f"Keys        : {list(data.keys())}")
        for k, v in data.items():
            print(f"  {k}: {str(v)[:300]}")
    elif isinstance(data, list):
        print(f"Response type: list ({len(data)} item(s))")
        if data:
            print(f"First item keys: {list(data[0].keys())}")
            for k, v in data[0].items():
                print(f"  {k}: {str(v)[:300]}")
    else:
        print(f"Unexpected type: {type(data)}")
        print(resp.text[:500])

    return 0


if __name__ == "__main__":
    sys.exit(main())
