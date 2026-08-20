## 1. Project Setup

- [x] 1.1 Initialise repo structure: create `src/`, `data/`, `demo/mirror/`, `.github/workflows/` directories
- [x] 1.2 Add `requirements.txt` with dependencies: `requests`, `jsonschema`, `python-dateutil`
- [x] 1.3 Add `.env.example` listing `BRIGHT_DATA_API_TOKEN` and `BRIGHT_DATA_COLLECTOR_ID` (no values)
- [x] 1.4 Add `.gitignore` entries for `.env`, `__pycache__/`, `*.pyc`, `data/previous.json`
- [x] 1.5 Enable GitHub Pages on the repo: Settings → Pages → Source: `main` branch, `/ (root)` — confirms the mirror URL `https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html` is reachable before building the demo workflow

## 2. Output Schema

- [x] 2.1 Write `data/schema.json` as a valid JSON Schema (Draft 7) defining required fields (`company_name`, `ticker`, `exchange`, `cmp`, `dividend_yield_pct`, `scraped_at`, `source_url`) and optional fields (`pe_ratio`, `market_cap_cr`, `roce_pct`, `roe_pct`, `sales_growth_pct`)
- [x] 2.2 Write `data/sample.json` with at least 3 realistic example records conforming to the schema, to serve as the hackathon's "example structured output" deliverable
- [x] 2.3 Add a schema validation helper `src/schema.py` with a `validate_record(record: dict)` function that raises `SchemaValidationError` on failure

## 3. Scraper API Client

- [x] 3.1 Create `src/scraper_client.py` with a `BrightDataClient` class
- [x] 3.2 Implement `BrightDataClient.__init__` — read `BRIGHT_DATA_API_TOKEN` and `BRIGHT_DATA_COLLECTOR_ID` from environment; raise `ConfigurationError` if either is missing
- [x] 3.3 Implement `trigger_run(target_url: str | None) -> str` — POST to `/dca/trigger` with collector ID and optional target URL override; return dataset ID
- [x] 3.4 Implement `poll_until_ready(dataset_id: str, poll_interval: int = 5, timeout: int = 300) -> str` — poll `/dca/dataset` endpoint; raise `TimeoutError` on timeout
- [x] 3.5 Implement `download_results(dataset_id: str, output_path: str = "data/latest.json") -> int` — download dataset, rotate existing `latest.json` → `previous.json`, write envelope JSON, return record count
- [x] 3.6 Add CLI entry point `src/run_scrape.py` that wires together `trigger_run → poll_until_ready → download_results` and prints a summary line

## 4. Data Diff Engine

- [x] 4.1 Create `src/diff_engine.py` with a `DiffEngine` class
- [x] 4.2 Implement `DiffEngine.load_snapshots(latest_path, previous_path) -> tuple[list, list]` — load both JSON envelopes; return empty list for missing previous
- [x] 4.3 Implement `DiffEngine.diff(latest: list, previous: list, thresholds: dict | None = None) -> DiffResult` — classify each ticker as ENTERED / EXITED / CHANGED / UNCHANGED using default thresholds from spec
- [x] 4.4 Implement `DiffEngine.write_report(diff_result: DiffResult, output_dir: str = "data") -> str` — append to `data/changes-YYYY-MM-DD.md` (create if absent); prepend a `## Run at HH:MM:SS UTC` header and `---` separator before each run's content; return the file path
- [x] 4.5 Add CLI entry point `src/run_diff.py` that runs the diff against the default snapshot paths and prints the report path

## 5. Self-Healing Demo Page

- [x] 5.1 Create `demo/mirror/index.html` — static HTML replicating the Screener.in dividend yield table structure with altered column headers (e.g. `"Div. Yield (%)"` instead of `"Dividend Yield"`) and an extra wrapping `<div>`
- [x] 5.2 Populate the mirror page with at least 5 sample rows of realistic fictional company data and add a visible `<!-- TEST FIXTURE — not live data -->` banner
- [x] 5.3 Verify that the original collector selector logic fails on the mirror page (document the failure mode in `demo/README.md`)

## 6. GitHub Actions Workflows

- [x] 6.1 Create `.github/workflows/scrape-on-merge.yml` — trigger on `push` to `main`, set `permissions: contents: write`, inject secrets as env vars, run `python src/run_scrape.py && python src/run_diff.py`, commit results with `[skip ci]`
- [x] 6.2 Ensure the commit step in `scrape-on-merge.yml` uses `git config user.email` and `git config user.name` for the bot identity before committing
- [x] 6.3 Create `.github/workflows/selfheal-demo.yml` — trigger on `workflow_dispatch`, hardcode `DEMO_TARGET_URL` to the GitHub Pages URL (`https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html`), run scraper against that URL, write results to `data/demo-latest.json`
- [x] 6.4 Add a `No-op on [skip ci]` check: confirm the `push` trigger in `scrape-on-merge.yml` does not re-fire on the bot's commit (GitHub natively skips workflows for commits containing `[skip ci]` — verify this is the case for the default `GITHUB_TOKEN`)

## 7. README

- [x] 7.1 Write `README.md` with sections: Overview, Architecture (Mermaid diagram), Setup & Configuration (env vars, secrets), Running Locally, GitHub Actions Automation, Self-Healing Demo (step-by-step), Output Schema reference, AI-Assistance Disclosure
- [x] 7.2 Add Mermaid diagram showing data flow: Screener.in → Scraper Studio → `scraper_client.py` → `data/latest.json` → `diff_engine.py` → `data/changes-<date>.md` → GitHub commit
- [x] 7.3 Add "Future Work" section mentioning NSE/BSE corporate announcements as a natural extension (no implementation)

## 8. Validation & Smoke Test

- [x] 8.1 Write `tests/test_schema.py` — validate that `data/sample.json` records pass `validate_record()` and that a record missing `ticker` raises `SchemaValidationError`
- [x] 8.2 Write `tests/test_diff_engine.py` — unit tests for ENTERED / EXITED / CHANGED / UNCHANGED classification and threshold logic using in-memory fixture data
- [x] 8.3 Write `tests/test_scraper_client.py` — test `ConfigurationError` on missing env vars; mock the Bright Data HTTP endpoints to test trigger, poll, and download logic without live API calls
- [ ] 8.4 Do a live end-to-end smoke test: set real secrets locally, run `python src/run_scrape.py`, confirm `data/latest.json` is written and passes schema validation
