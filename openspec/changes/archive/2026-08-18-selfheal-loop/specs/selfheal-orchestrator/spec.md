## ADDED Requirements

### Requirement: Exit early when initial scrape is healthy
The system SHALL exit with code 0 and log a "healthy" message when the first health check passes, without triggering any refactor steps.

#### Scenario: First download is healthy
- **WHEN** `run_selfheal.py` downloads results and `health_check` returns `HealthStatus.HEALTHY`
- **THEN** the script logs "Scrape is healthy — no self-heal needed" and exits with code 0 without calling `refactor_template`

### Requirement: Trigger self-heal on degraded or broken result
The system SHALL invoke the page analyser, call `refactor_template`, poll for completion, and approve the rewrite when the initial health check returns `DEGRADED` or `BROKEN`.

#### Scenario: Broken result triggers full self-heal cycle
- **WHEN** the first health check returns `HealthStatus.BROKEN`
- **THEN** the orchestrator calls `analyse_page`, then `refactor_template`, then `poll_refactor`, then `approve_refactor` in sequence

### Requirement: Re-trigger and verify recovery after refactor
After approving the refactor, the system SHALL re-trigger the collector, wait for it to be ready, re-download results, and run a second health check.

#### Scenario: Re-trigger after refactor approval
- **WHEN** `approve_refactor` completes successfully
- **THEN** the orchestrator calls `trigger_run`, `poll_until_ready`, and `download_results` again, followed by a second `health_check`

### Requirement: Print structured summary at termination
The system SHALL print (via `logging`) a structured summary before exit that includes: original health status, fix prompt sent (or "N/A" if healthy), and recovery status.

#### Scenario: Summary on successful recovery
- **WHEN** the second health check returns `HealthStatus.HEALTHY`
- **THEN** the log output includes original status, the fix prompt text, and recovery status "recovered"

#### Scenario: Summary on failed recovery
- **WHEN** the second health check returns `DEGRADED` or `BROKEN`
- **THEN** the log output includes original status, fix prompt text, and recovery status "failed", and the script exits with a non-zero code

### Requirement: Loop runs at most twice
The self-heal attempt SHALL occur at most once. If the second health check still fails, the orchestrator SHALL exit with a non-zero code and SHALL NOT trigger a third attempt.

#### Scenario: No indefinite retry
- **WHEN** both the first and second health checks return `BROKEN`
- **THEN** the orchestrator exits with a non-zero code after exactly two download-and-check cycles

### Requirement: Accept optional target_url CLI argument
The system SHALL accept an optional `--target-url` argument from the command line, defaulting to the live Screener.in screen URL when not provided.

#### Scenario: Default URL used when no argument given
- **WHEN** `run_selfheal.py` is invoked without `--target-url`
- **THEN** the scraper uses the default target URL configured in `BrightDataClient`

#### Scenario: Custom URL overrides default
- **WHEN** `run_selfheal.py` is invoked with `--target-url https://example.com/test`
- **THEN** that URL is passed to `trigger_run` and `analyse_page`

### Requirement: Output written to data/latest.json
The system SHALL write downloaded results to `data/latest.json` using the same envelope format as `run_scrape.py`. The format SHALL NOT be altered.

#### Scenario: Same output path as run_scrape.py
- **WHEN** `run_selfheal.py` completes a download cycle
- **THEN** `data/latest.json` exists and contains a valid envelope with `meta` and `records` keys
