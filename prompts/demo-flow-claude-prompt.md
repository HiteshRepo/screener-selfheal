# Claude CLI Prompt — Alternating Mirror Demo Flow

Paste this as your opening prompt to Claude Code (`claude` CLI) inside the `screener-selfheal` project directory. Read the full codebase before proposing anything.

---

## PROMPT

I'm extending an existing project: `https://github.com/HiteshRepo/screener-selfheal`. Read the full codebase before proposing anything — especially `demo/mirror/index.html`, `.github/workflows/selfheal-loop.yml`, `.github/workflows/selfheal-demo.yml`, and `src/run_selfheal.py`.

### Context: what already exists

- A static mirror page at `demo/mirror/index.html` with a deliberately altered HTML structure (renamed CSS classes, extra wrapper divs, renamed column headers) deployed on GitHub Pages at `https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html`
- `selfheal-loop.yml` — manual-dispatch GitHub Actions workflow that runs `src/run_selfheal.py` against a configurable target URL, commits results, and opens a PR
- `src/run_selfheal.py` — automated self-heal loop: trigger scrape → health check → if broken, analyse page with OpenAI → refactor Bright Data collector → re-scrape → verify recovery
- Two separate collectors:
  - `BRIGHT_DATA_COLLECTOR_ID` — production collector, configured for Screener.in, used by `scrape-on-merge.yml`. Never touch this in the demo flow.
  - `BRIGHT_DATA_DEMO_COLLECTOR_ID` — demo collector, configured for the mirror page. Used exclusively by the demo workflows.

### What we're building

A **repeatable, reset-free demo flow** using two alternate mirror page layouts. The same GitHub Pages URL always serves the mirror, but each demo run swaps to the opposite layout — so the demo collector is always chasing a layout it hasn't seen yet.

#### 1. Two mirror page layouts

Create `demo/mirror/v1.html` and `demo/mirror/v2.html`. Both must:
- Visually display the same dividend yield stock data (use the same sample rows as `data/sample.json`)
- Be structurally different enough that a CSS/XPath selector built for one will fail on the other

Suggested differences between v1 and v2:

| Element | v1 | v2 |
|---|---|---|
| Table CSS class | `class="data-table"` | `class="screener-mirror"` |
| Wrapper div | Table is direct child of `<div id="result">` | Table is nested inside `.table-outer-wrapper > .table-inner-container` |
| Dividend yield header | `Dividend Yield` | `Div. Yield (%)` |
| Column order | ROCE / ROE after Dividend Yield | ROCE / ROE before Div. Yield (%) |

`demo/mirror/index.html` is the live file served by GitHub Pages. It should initially be a copy of `v1.html`.

#### 2. `break-mirror.yml` workflow

A manual-dispatch GitHub Actions workflow (`workflow_dispatch`) that:

1. Reads which version is currently live by inspecting `demo/mirror/index.html` (e.g. check for a comment `<!-- layout: v1 -->` or `<!-- layout: v2 -->` in the file)
2. Copies the alternate version (`v1` → deploy `v2`, or `v2` → deploy `v1`) to `demo/mirror/index.html`
3. Commits and pushes directly to `main` with message `chore: switch mirror layout to v<N> [skip ci]`
4. Outputs which layout is now live as a workflow summary step

#### 3. Update `selfheal-loop.yml`

- Add a `wait_for_pages` step after checkout that sleeps 30 seconds (to allow GitHub Pages propagation) — only when triggered after `break-mirror.yml`. Add a boolean input `pages_just_updated` (default: `false`); sleep only when `true`.
- Use `BRIGHT_DATA_DEMO_COLLECTOR_ID` (not `BRIGHT_DATA_COLLECTOR_ID`) when the target URL is the mirror page. If `target_url` input contains `github.io`, automatically switch to the demo collector ID.
- Default `target_url` for this workflow should be `https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html`

#### Demo run sequence

```
1. break-mirror.yml        → flips mirror from vN to vM, commits to main
2. (GitHub Pages propagates ~30s)
3. selfheal-loop.yml       → triggered with pages_just_updated=true
                             uses BRIGHT_DATA_DEMO_COLLECTOR_ID
                             scrapes mirror → health check fails (wrong selectors)
                             → OpenAI analyses mirror vM → generates fix prompt
                             → refactors demo collector → re-scrapes → recovers
                             → commits results, opens PR
```

Next demo run does the same in reverse (vM → vN). No manual reset needed.

### Constraints

- Do not touch `scrape-on-merge.yml` or the production collector (`BRIGHT_DATA_COLLECTOR_ID`)
- Do not modify `src/run_selfheal.py` — all changes are in workflows and mirror HTML files
- The two layout files must include a machine-readable layout marker comment (`<!-- layout: v1 -->` / `<!-- layout: v2 -->`) as the first line inside `<body>` so `break-mirror.yml` can detect the current version without parsing HTML
- Follow existing workflow style (Python 3.11, `actions/checkout@v4`, `actions/setup-python@v5`)

### Tests

No new Python tests are needed — this change is purely HTML + GitHub Actions workflows. Verify correctness by dry-running `break-mirror.yml` logic manually: confirm the version detection and file-swap steps are correct before pushing.
