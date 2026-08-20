## Why

The existing dividend portfolio tracker (`stock-screeners`) requires manual visits to Screener.in to refresh data — a tedious, error-prone process that defeats the purpose of a systematic tracking approach. This change automates the full data lifecycle: scrape → diff → flag changes, and demonstrates Bright Data Scraper Studio's self-healing capability for the "Into the Scrape-Verse" hackathon submission.

## What Changes

- Introduce a Bright Data Scraper Studio API client that triggers the existing collector (`c_msvhzc3s2gixuk6k42`), polls for completion, and downloads structured JSON results
- Define and enforce a canonical output schema (JSON) for scraped dividend yield data (one record per company per scrape)
- Add a data diff engine that compares fresh scrape output against stored state and surfaces meaningful changes (new dividend, yield threshold crossed, company entered/left the screen)
- Add a GitHub Actions workflow (`scrape-on-merge.yml`) that auto-runs the scraper on push to `main` and commits `data/latest.json` back to the repo — turning git history into a scrape audit log
- Add a second workflow / manual-dispatch job for the self-healing demo (points the collector at a deliberately modified/mirrored version of the target page)
- Write a README covering setup, Scraper Studio usage, self-healing demo instructions, architecture, and AI-assistance disclosure

## Capabilities

### New Capabilities

- `scraper-api-client`: Trigger, poll, and download Bright Data Scraper Studio collector results via the `/dca/trigger` + `/dca/dataset` API; handles auth, retries, and result persistence to `data/latest.json`
- `output-schema`: Canonical JSON schema for one scraped record (company name, ticker, CMP, dividend yield %, P/E, market cap, extra ratio columns, `scraped_at`, `source_url`); used as both the deliverable sample and the tracker's input contract
- `data-diff-engine`: Compares new `data/latest.json` against previously stored state, emits a human-readable change report (new dividend declared, yield moved past threshold, company entered/left screen) consistent with the tracker's advisory-only, markdown-file-based style
- `github-actions-automation`: Two GitHub Actions workflows — `scrape-on-merge.yml` (auto-scrape on push to main, commit results back with `[skip ci]`) and `selfheal-demo.yml` (manual-dispatch run against a modified/mirrored target page for the demo)
- `selfheal-demo`: A static mirrored/modified copy of the Screener.in target page with an altered layout, used to demonstrate the scraper detecting layout mismatch and recovering via Scraper Studio's self-healing flow; includes before/after evidence for the demo video

### Modified Capabilities

<!-- No existing specs to modify — this is a greenfield repo -->

## Impact

- New files: `src/scraper_client.py` (or `.js`), `src/diff_engine.py`, `data/latest.json`, `data/schema.json`, `.github/workflows/scrape-on-merge.yml`, `.github/workflows/selfheal-demo.yml`, `demo/mirror/index.html`, `README.md`
- Reads/writes `data/latest.json` and `data/previous.json` within this repo; change reports written as `data/changes-<date>.md` matching the markdown-file style of `stock-screeners`
- External dependency: Bright Data API (token via `BRIGHT_DATA_API_TOKEN` repo secret, collector ID via `BRIGHT_DATA_COLLECTOR_ID` repo secret)
- No changes to `stock-screeners` repo itself; format compatibility is enforced by `output-schema` so data can be consumed by either repo's tooling
