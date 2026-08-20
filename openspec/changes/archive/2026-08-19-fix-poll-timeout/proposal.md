## Why

`poll_until_ready()` in `src/scraper_client.py` polls the Bright Data dataset endpoint without the `format=json` parameter, causing it to receive a raw NDJSON stream instead of a status JSON. When the dataset has zero records (i.e., the collector is broken), the response body is empty, `response.json()` raises `ValueError`, and the code incorrectly treats this as "still warming up" — looping for the full 300s timeout before failing. This causes every GitHub Actions scrape run to time out rather than fail fast or trigger self-healing.

## What Changes

- Fix `poll_until_ready()` to add `format=json` to request params, and switch the ready condition from parsing a `status` field to checking the HTTP status code (202 = still building, 200 = ready)
- Update `tests/test_scraper_client.py` with tests covering the corrected polling logic
- No changes to any other module, workflow, or documentation

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- `bright-data-client`: The polling behaviour of `poll_until_ready()` changes — it now uses `format=json` and HTTP status codes to detect readiness instead of parsing a `status` field from the response body. This is a behavioural fix, not a new requirement.

## Impact

- **`src/scraper_client.py`**: `poll_until_ready()` — add `"format": "json"` param, change ready-detection logic
- **`tests/test_scraper_client.py`**: add / update tests for the corrected polling flow
- **GitHub Actions (`scrape-on-merge.yml`, `selfheal-loop.yml`)**: no workflow changes needed; fixing the client unblocks both workflows
- **No new dependencies**
