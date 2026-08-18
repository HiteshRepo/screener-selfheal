# Testing Guide

## Prerequisites

Python 3.11+ and a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
pip install pytest
```

---

## Unit & Integration Tests (no secrets required)

Run all tests:

```bash
.venv/bin/python -m pytest tests/ -v
```

Run a specific test file:

```bash
.venv/bin/python -m pytest tests/test_schema.py -v
.venv/bin/python -m pytest tests/test_diff_engine.py -v
.venv/bin/python -m pytest tests/test_scraper_client.py -v
```

Run a single test by name:

```bash
.venv/bin/python -m pytest tests/test_diff_engine.py::TestDiffChanged::test_dividend_yield_change_above_threshold_classified_changed -v
```

### What is covered

| File | Coverage |
|---|---|
| `tests/test_schema.py` | `validate_record()` happy paths, missing required fields, wrong types; all `data/sample.json` records pass |
| `tests/test_diff_engine.py` | ENTERED / EXITED / CHANGED / UNCHANGED classification, threshold overrides, `write_report()` output |
| `tests/test_scraper_client.py` | `ConfigurationError` on missing env vars; mocked `trigger_run`, `poll_until_ready`, `download_results` |

---

## Live End-to-End Smoke Test (real secrets required)

### 1. Set secrets

```bash
cp .env.example .env
# Open .env and fill in:
#   BRIGHT_DATA_API_TOKEN=<your token>
#   BRIGHT_DATA_COLLECTOR_ID=<your collector ID>
```

### 2. Export secrets to the shell

```bash
set -a && source .env && set +a
```

### 3. Run the scraper

```bash
.venv/bin/python src/run_scrape.py
```

Expected output:

```
Scrape complete — dataset_id=<id>, records=<N>, written to data/latest.json
```

### 4. Validate the output against the schema

```bash
.venv/bin/python - <<'EOF'
import json, sys
sys.path.insert(0, 'src')
from schema import validate_record, SchemaValidationError

with open('data/latest.json', encoding='utf-8') as fh:
    envelope = json.load(fh)

records = envelope.get('records', [])
meta = envelope.get('meta', {})

assert meta.get('record_count') == len(records), \
    f"meta.record_count {meta.get('record_count')} != len(records) {len(records)}"

for i, record in enumerate(records):
    validate_record(record)

print(f"OK — {len(records)} record(s) validated, meta.record_count matches.")
EOF
```

### 5. Run the diff engine

```bash
.venv/bin/python src/run_diff.py
```

Expected output (first run):

```
Diff report written to data/changes-<YYYY-MM-DD>.md
```

Check the report:

```bash
cat data/changes-$(date +%Y-%m-%d).md
```

---

## Self-Heal Loop

The self-heal loop downloads scrape results, checks data health, and — if unhealthy — uses OpenAI to analyse the target page and refactor the Bright Data collector template automatically before re-running.

### Required secrets

| Variable | Description |
|---|---|
| `BRIGHT_DATA_API_TOKEN` | Bright Data API token |
| `BRIGHT_DATA_COLLECTOR_ID` | Collector ID for the screener scraper |
| `OPENAI_API_KEY` | OpenAI API key (used by the page analyser) |

Set them in `.env`:

```bash
cp .env.example .env
# Fill in BRIGHT_DATA_API_TOKEN, BRIGHT_DATA_COLLECTOR_ID, OPENAI_API_KEY
set -a && source .env && set +a
```

### Unit tests (no secrets required)

Test the health-check module:

```bash
make test-health
# or directly:
.venv/bin/python -m pytest tests/test_health_check.py -v
```

Test the page-analyser module (all external calls are mocked):

```bash
make test-analyser
# or directly:
.venv/bin/python -m pytest tests/test_page_analyser.py -v
```

### Local end-to-end run (real secrets required)

```bash
make selfheal
# or directly:
set -a && source .env && set +a
.venv/bin/python src/run_selfheal.py
```

Override the target URL analysed by the page analyser:

```bash
.venv/bin/python src/run_selfheal.py --target-url https://www.screener.in/screens/dividend-yield/
```

### Expected output at each step

**Step 1 — first download cycle**

```
INFO scraper_client: Triggering run for collector <id>
INFO scraper_client: Polling dataset <dataset_id> …
INFO scraper_client: Dataset ready — <N> records; writing to data/latest.json
```

**Step 2 — initial health check**

Healthy path (no self-heal needed):

```
INFO run_selfheal: Initial health: status=HEALTHY reason=All <N> records passed validation
INFO run_selfheal: SUMMARY | original_status=HEALTHY | fix_prompt=N/A | recovery_status=not_needed
INFO run_selfheal: Scrape is healthy — no self-heal needed.
```

Unhealthy path (self-heal triggered):

```
INFO run_selfheal: Initial health: status=BROKEN reason=<reason>
```

**Step 3 — page analysis (unhealthy path only)**

```
INFO page_analyser: Fetching target page https://www.screener.in/screens/dividend-yield/
INFO page_analyser: Calling OpenAI gpt-4o for fix description
INFO run_selfheal: Page analysis complete — fix_prompt length=<N>
```

**Step 4 — template refactor (unhealthy path only)**

```
INFO scraper_client: Submitting refactor job — prompt length=<N>
INFO scraper_client: Polling refactor job <job_id> …
INFO scraper_client: Refactor job done; approving
```

**Step 5 — second download cycle and final health check (unhealthy path only)**

Recovery succeeded:

```
INFO run_selfheal: Second health: status=HEALTHY reason=All <N> records passed validation
INFO run_selfheal: SUMMARY | original_status=BROKEN | fix_prompt=<prompt> | recovery_status=recovered
```

Recovery failed:

```
INFO run_selfheal: Second health: status=BROKEN reason=<reason>
INFO run_selfheal: SUMMARY | original_status=BROKEN | fix_prompt=<prompt> | recovery_status=failed
ERROR run_selfheal: Recovery failed — second health check: <reason>
```

Exit code is `0` on success, `1` on any failure or unrecovered unhealthy state.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: jsonschema` | Run `pip install -r requirements.txt` inside the venv |
| `ConfigurationError: BRIGHT_DATA_API_TOKEN is not set` | Export env vars: `set -a && source .env && set +a` |
| `TimeoutError` during poll | Collector may be slow; increase timeout: `TIMEOUT=600 python src/run_scrape.py` |
| `data/latest.json` missing after scrape | Check `src/run_scrape.py` logs for API errors |
