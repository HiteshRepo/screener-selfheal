# Setup & Configuration

## Prerequisites

- Python 3.10+
- A Bright Data account with a Scraper Studio collector for the Screener.in dividend screen

## Environment Variables

Copy `.env.example` and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `BRIGHT_DATA_API_TOKEN` | Yes | Bright Data API bearer token |
| `BRIGHT_DATA_COLLECTOR_ID` | Yes | Scraper Studio collector ID (e.g. `c_msvhzc3s2gixuk6k42`) |

## Install Dependencies

```bash
pip install -r requirements.txt
```

## GitHub Repository Secrets

Add the following secrets in **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `BRIGHT_DATA_API_TOKEN` | Your Bright Data API token |
| `BRIGHT_DATA_COLLECTOR_ID` | Your collector ID |

## Component Reference

| File | Role |
|---|---|
| `src/scraper_client.py` | `BrightDataClient` — trigger, poll, download, rotate snapshots |
| `src/run_scrape.py` | CLI entry point: wires trigger → poll → download |
| `src/diff_engine.py` | `DiffEngine` — loads snapshots, classifies changes, writes report |
| `src/run_diff.py` | CLI entry point: runs diff against default paths |
| `src/schema.py` | `validate_record()` — JSON Schema (Draft 7) validation helper |
| `data/schema.json` | Machine-readable canonical record schema |
| `data/sample.json` | Example records conforming to the schema |
| `.github/workflows/scrape-on-merge.yml` | Auto-scrape on push to `main`, commit results |
| `.github/workflows/selfheal-demo.yml` | Manual-dispatch demo run against the mirror page |
| `demo/mirror/index.html` | Static mirror with altered DOM layout for self-heal demo |

## Running Locally

```bash
# Scrape: trigger collector, poll until ready, download results
python src/run_scrape.py

# Diff: compare latest vs previous snapshot, write change report
python src/run_diff.py
```

Output files:

- `data/latest.json` — current scrape (envelope with `meta` + `records`)
- `data/previous.json` — prior scrape (rotated automatically before each new download)
- `data/changes-YYYY-MM-DD.md` — appended change report for today

### Run schema validation manually

```python
from src.schema import validate_record
validate_record({"company_name": "Infosys", "ticker": "INFY", ...})
```
