## Why

Phase 1 delivers a scraper that downloads results and detects schema drift, but when the collector returns broken or empty data there is no automated recovery path — an engineer must manually inspect and repair the Bright Data collector script. Phase 2 closes that gap by implementing an LLM-driven self-healing loop that detects failures, diagnoses the DOM change, generates a repair prompt, and drives Bright Data's AI Flow API to rewrite and re-approve the collector — all without human intervention.

## What Changes

- **New module** `src/health_check.py` — inspects a downloaded envelope and returns a structured `HealthReport` (healthy / degraded / broken) with a failure-reason string.
- **New module** `src/page_analyser.py` — fetches the target page HTML via `requests` and calls the OpenAI API (`gpt-4o`) to produce a concise fix description (≤900 chars) describing what changed in the DOM relative to the expected schema fields.
- **Extended** `src/scraper_client.py` — adds `refactor_template()`, `poll_refactor()`, and `approve_refactor()` methods to drive Bright Data's AI Flow API.
- **New entry point** `src/run_selfheal.py` — CLI orchestrator wiring: download → health check → page analyse → refactor → poll → approve → re-trigger → re-download → final health check. Runs the loop **at most twice** (one attempt + one verification).
- **New workflow** `.github/workflows/selfheal-loop.yml` — `workflow_dispatch` with optional `target_url` input; injects `BRIGHT_DATA_API_TOKEN`, `BRIGHT_DATA_COLLECTOR_ID`, `OPENAI_API_KEY`; commits results back with `[skip ci]`.
- **New tests** `tests/test_health_check.py`, `tests/test_page_analyser.py` — fully mocked, no live API calls.
- **Updated** `Makefile` — adds `selfheal`, `test-health`, `test-analyser` targets.
- **Updated** `TESTING.md` — adds self-heal loop section with local-run instructions, required secrets, and expected output.
- **Updated** `.env.example` — adds `ANTHROPIC_API_KEY` entry.

## Capabilities

### New Capabilities

- `health-check`: Inspects a downloaded scrape envelope and classifies it as healthy, degraded, or broken based on record count, schema validation, and field completeness.
- `page-analyser`: Fetches live page HTML and uses the OpenAI API to identify DOM structural changes relative to the canonical schema, returning a fix description for the Bright Data refactor prompt.
- `selfheal-orchestrator`: End-to-end self-healing loop — detects failure, triggers LLM diagnosis, drives Bright Data AI Flow API (refactor → approve), re-scrapes, and verifies recovery.

### Modified Capabilities

- `bright-data-client`: Adds AI Flow API methods (`refactor_template`, `poll_refactor`, `approve_refactor`) to the existing `BrightDataClient`. The existing scrape-trigger and poll behavior is unchanged; new methods extend the client's surface without altering existing call signatures.

## Impact

- **New dependency**: `openai` Python SDK (added to `requirements.txt`).
- **New secret**: `OPENAI_API_KEY` — required in `.env` for local runs and as a GitHub Actions secret for CI.
- **Existing data format unchanged**: `run_selfheal.py` writes to the same `data/latest.json` envelope as `run_scrape.py`.
- **Bright Data plan prerequisite**: The `refactor_template` and `resume_automation_job` endpoints must be available on the account's Bright Data plan; if not, the orchestrator exits with a clear error and the fallback is manual repair (no silent failure).
- **No new scraping libraries**: `requests` only — HTML parsing for selector analysis is delegated entirely to the OpenAI model.
