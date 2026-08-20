# Selfheal Loop Workflow

## Purpose

The selfheal-loop workflow is a GitHub Actions workflow that orchestrates the self-heal cycle: it triggers a scrape against a configurable target URL, selects the appropriate Bright Data collector (demo vs. production), and optionally delays to allow GitHub Pages propagation before scraping.

## Requirements

### Requirement: selfheal-loop-workflow accepts pages_just_updated input
`.github/workflows/selfheal-loop.yml` SHALL accept a boolean `workflow_dispatch` input `pages_just_updated` (default: `false`). When `true`, the workflow SHALL sleep 30 seconds before triggering the scrape to allow GitHub Pages propagation.

#### Scenario: pages_just_updated false — no delay
- **WHEN** `selfheal-loop.yml` is triggered with `pages_just_updated` omitted or set to `false`
- **THEN** the workflow proceeds immediately without any sleep step

#### Scenario: pages_just_updated true — 30s delay
- **WHEN** `selfheal-loop.yml` is triggered with `pages_just_updated: true`
- **THEN** the workflow sleeps 30 seconds before running `src/run_selfheal.py`

### Requirement: selfheal-loop-workflow auto-selects demo collector for github.io URLs
`.github/workflows/selfheal-loop.yml` SHALL use `BRIGHT_DATA_DEMO_COLLECTOR_ID` as the `BRIGHT_DATA_COLLECTOR_ID` environment variable when the `target_url` input contains `github.io`, and `BRIGHT_DATA_COLLECTOR_ID` otherwise.

#### Scenario: Mirror URL triggers demo collector
- **WHEN** `target_url` is `https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html`
- **THEN** `run_selfheal.py` runs with `BRIGHT_DATA_COLLECTOR_ID` set to the value of the `BRIGHT_DATA_DEMO_COLLECTOR_ID` secret

#### Scenario: Non-mirror URL uses production collector
- **WHEN** `target_url` is empty or contains `screener.in`
- **THEN** `run_selfheal.py` runs with `BRIGHT_DATA_COLLECTOR_ID` set to the value of the `BRIGHT_DATA_COLLECTOR_ID` secret

### Requirement: selfheal-loop-workflow default target URL is the mirror page
The `target_url` input SHALL default to `https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html` so the workflow is demo-ready without manual input.

#### Scenario: Default target URL used when input omitted
- **WHEN** `selfheal-loop.yml` is triggered without specifying `target_url`
- **THEN** `run_selfheal.py` is called with `--target-url https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html`
