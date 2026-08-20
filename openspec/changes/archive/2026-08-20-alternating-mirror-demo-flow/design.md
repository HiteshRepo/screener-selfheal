## Context

The existing self-heal loop (`run_selfheal.py` + `selfheal-loop.yml`) works correctly but has no repeatable demo trigger. The mirror page (`demo/mirror/index.html`) is static — once the demo collector adapts to it, subsequent runs succeed immediately and the self-heal path is never reached again. Resetting requires manually reverting the collector template in Bright Data Scraper Studio UI, which is not scriptable and breaks the demo narrative.

The production flow (Screener.in + `BRIGHT_DATA_COLLECTOR_ID` + `scrape-on-merge.yml`) is unrelated and must not be touched.

## Goals / Non-Goals

**Goals:**
- Make the self-heal loop demo fully repeatable without any manual reset
- Keep the same GitHub Pages URL for the mirror — only the served HTML changes
- Isolate demo from production: separate collector, separate workflows
- No changes to `src/` Python code or tests

**Non-Goals:**
- Dynamic/server-side HTML generation (GitHub Pages is static only)
- Automated collector template reset (alternating layouts make this unnecessary)
- Changes to the production scrape pipeline

## Decisions

**Decision 1: Two static HTML files swapped by a workflow, not dynamic serving**

Alternatives considered:
- Query-param-driven layout switching via JavaScript — rejected because Bright Data executes JS but selector rules are evaluated against the final DOM; the selector logic is identical regardless of JS execution, making it unreliable for testing selector failure
- Server-side rendering with a separate host — rejected as over-engineering for a hackathon demo fixture

Chosen: Two complete HTML files (`v1.html`, `v2.html`). A workflow copies the alternate version to `index.html` and commits. GitHub Pages serves the new file within ~30s.

**Decision 2: Layout version detected via inline comment, not a separate state file**

A comment `<!-- layout: v1 -->` or `<!-- layout: v2 -->` as the first line inside `<body>` lets the `break-mirror.yml` workflow detect the current version with a single `grep` without maintaining a separate state file that could drift out of sync.

**Decision 3: Auto-select demo collector by URL pattern in `selfheal-loop.yml`**

When `target_url` contains `github.io`, the workflow uses `BRIGHT_DATA_DEMO_COLLECTOR_ID` instead of `BRIGHT_DATA_COLLECTOR_ID`. This avoids a separate demo workflow and keeps the URL as the single source of truth for which collector to use.

**Decision 4: 30s Pages propagation wait gated by a `pages_just_updated` boolean input**

A hardcoded `sleep 30` would slow all workflow runs. Making it opt-in (default: `false`) means normal self-heal runs are unaffected; the demo sequence sets it to `true` when chaining after `break-mirror.yml`.

## Risks / Trade-offs

- **GitHub Pages propagation delay is not guaranteed at 30s** → Mitigation: 30s is conservative for a small HTML file; the demo can retry if a run catches a stale page
- **After many cycles the collector may over-fit to alternating layouts** → Mitigation: two layouts is sufficient for a hackathon demo; this is not a production concern
- **`break-mirror.yml` commit triggers `scrape-on-merge.yml`** → Mitigation: commit message includes `[skip ci]` to suppress the production workflow
