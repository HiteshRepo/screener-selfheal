## ADDED Requirements

### Requirement: Scrape-on-merge workflow
A GitHub Actions workflow file `scrape-on-merge.yml` SHALL trigger automatically on every push to the `main` branch, run the full scrape pipeline (trigger → poll → download → diff), and commit the results back to the repo.

#### Scenario: Push to main triggers workflow
- **WHEN** any commit is pushed to the `main` branch
- **THEN** the `scrape-on-merge` workflow starts within GitHub Actions

#### Scenario: Results committed back to repo
- **WHEN** the scrape pipeline completes successfully
- **THEN** the workflow commits `data/latest.json` and `data/changes-<date>.md` to `main` with the message `chore: scrape results [skip ci]`

#### Scenario: Skip-CI prevents infinite loop
- **WHEN** the bot's own commit (containing `[skip ci]`) is pushed
- **THEN** GitHub Actions does NOT re-trigger the workflow

#### Scenario: Workflow fails on scraper error
- **WHEN** the scraper client raises an exception (e.g., timeout, API error)
- **THEN** the workflow exits with a non-zero code and no commit is made

### Requirement: Secrets and configuration via environment
The workflow SHALL read all sensitive values from GitHub Actions secrets and MUST NOT hardcode any token or ID in the workflow YAML.

#### Scenario: API token injected from secrets
- **WHEN** the workflow runs
- **THEN** `BRIGHT_DATA_API_TOKEN` is sourced from the `BRIGHT_DATA_API_TOKEN` repository secret and passed to the scraper script as an environment variable

#### Scenario: Collector ID injected from secrets
- **WHEN** the workflow runs
- **THEN** `BRIGHT_DATA_COLLECTOR_ID` is sourced from the `BRIGHT_DATA_COLLECTOR_ID` repository secret

#### Scenario: Missing secret causes workflow failure
- **WHEN** either required secret is absent from the repository
- **THEN** the scraper client raises `ConfigurationError` and the workflow exits non-zero

### Requirement: Manual self-healing demo workflow
A second GitHub Actions workflow file `selfheal-demo.yml` SHALL be triggerable via `workflow_dispatch` (manual run) and SHALL point the scraper at the static mirror URL for the self-healing demo.

#### Scenario: Manual trigger via workflow_dispatch
- **WHEN** a maintainer triggers the `selfheal-demo` workflow from the Actions UI
- **THEN** the workflow starts and runs the scraper against the mirror URL

#### Scenario: Demo target URL overrides default
- **WHEN** the `selfheal-demo` workflow runs
- **THEN** the scraper client uses `DEMO_TARGET_URL` (provided as a workflow input or hardcoded mirror URL) instead of the production Screener.in URL

#### Scenario: Demo results written to separate path
- **WHEN** the `selfheal-demo` workflow completes
- **THEN** results are written to `data/demo-latest.json` to avoid overwriting production data

### Requirement: Workflow permissions
Both workflows SHALL declare explicit `permissions` blocks granting only the minimum required access.

#### Scenario: contents:write permission declared
- **WHEN** either workflow attempts to commit results back
- **THEN** the `permissions.contents` is set to `write` and all other permissions are left at their defaults (`read` or omitted)
