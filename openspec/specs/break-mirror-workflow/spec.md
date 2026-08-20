# Break Mirror Workflow

## Purpose

The break-mirror workflow is a manually triggered GitHub Actions workflow that alternates the demo mirror layout by detecting which layout is currently live and deploying the opposite one. This drives the self-heal demo cycle by deliberately breaking the active scraper selectors.

## Requirements

### Requirement: break-mirror workflow detects current layout and deploys the alternate
`.github/workflows/break-mirror.yml` SHALL be a `workflow_dispatch` workflow that reads the layout marker from `demo/mirror/index.html`, copies the opposite layout file to `demo/mirror/index.html`, and commits + pushes to `main` with `[skip ci]` in the commit message.

#### Scenario: Current layout is v1, workflow deploys v2
- **WHEN** `demo/mirror/index.html` contains `<!-- layout: v1 -->` and the workflow is triggered
- **THEN** `demo/mirror/index.html` is replaced with the contents of `demo/mirror/v2.html` and committed with message `chore: switch mirror layout to v2 [skip ci]`

#### Scenario: Current layout is v2, workflow deploys v1
- **WHEN** `demo/mirror/index.html` contains `<!-- layout: v2 -->` and the workflow is triggered
- **THEN** `demo/mirror/index.html` is replaced with the contents of `demo/mirror/v1.html` and committed with message `chore: switch mirror layout to v1 [skip ci]`

#### Scenario: Workflow summary reports new layout
- **WHEN** the workflow completes
- **THEN** a GitHub Actions step summary is written stating which layout is now live (e.g. `Mirror is now layout v2`)

### Requirement: break-mirror commit does not trigger production scrape workflow
The commit pushed by `break-mirror.yml` SHALL include `[skip ci]` in its message so `scrape-on-merge.yml` is not triggered.

#### Scenario: skip ci tag suppresses scrape-on-merge
- **WHEN** the break-mirror commit is pushed to `main`
- **THEN** `scrape-on-merge.yml` does not start a new run (GitHub skips workflows for commits containing `[skip ci]` with the default `GITHUB_TOKEN`)
