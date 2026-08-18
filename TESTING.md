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

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: jsonschema` | Run `pip install -r requirements.txt` inside the venv |
| `ConfigurationError: BRIGHT_DATA_API_TOKEN is not set` | Export env vars: `set -a && source .env && set +a` |
| `TimeoutError` during poll | Collector may be slow; increase timeout: `TIMEOUT=600 python src/run_scrape.py` |
| `data/latest.json` missing after scrape | Check `src/run_scrape.py` logs for API errors |
