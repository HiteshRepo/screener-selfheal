## Why

The self-heal loop demo has no repeatable trigger: the mirror page is static, and after one successful self-heal run the demo collector is already adapted and cannot be re-triggered without a manual reset in Bright Data Scraper Studio. This blocks live hackathon demos. Two alternating mirror layouts fix this — each run flips to the opposite layout, giving the demo collector a fresh mismatch to heal every time.

## What Changes

- Add `demo/mirror/v1.html` and `demo/mirror/v2.html` — two structurally distinct layouts of the same dividend data, each with a machine-readable layout marker comment
- Add `demo/mirror/index.html` seeded as a copy of `v1.html` (the live GitHub Pages file)
- Add `.github/workflows/break-mirror.yml` — detects current live layout, deploys the alternate version, commits to `main`
- Update `.github/workflows/selfheal-loop.yml` — add `pages_just_updated` input for a 30s propagation wait, and auto-select `BRIGHT_DATA_DEMO_COLLECTOR_ID` when the target URL contains `github.io`

## Capabilities

### New Capabilities

- `alternating-mirror-layouts`: Two structurally different HTML mirror pages (`v1`, `v2`) that share the same GitHub Pages URL but break each other's collector selectors
- `break-mirror-workflow`: GitHub Actions workflow that detects the current live layout version and atomically swaps to the opposite one

### Modified Capabilities

- `selfheal-loop-workflow`: Adds `pages_just_updated` boolean input and demo-collector auto-selection logic

## Impact

- `demo/mirror/` — new files `v1.html`, `v2.html`; `index.html` reseeded from `v1.html`
- `.github/workflows/break-mirror.yml` — new workflow
- `.github/workflows/selfheal-loop.yml` — two new inputs and collector-selection logic
- No changes to `src/`, tests, production collector (`BRIGHT_DATA_COLLECTOR_ID`), or `scrape-on-merge.yml`
- Requires `BRIGHT_DATA_DEMO_COLLECTOR_ID` and `OPENAI_API_KEY` repo secrets (already needed by existing self-heal workflows)
