## Context

The existing dividend portfolio tracker (`stock-screeners` repo) is a Python CLI that reads and writes local Markdown files. Data is refreshed manually by the user visiting Screener.in. This change adds an automated data layer in the new `screener-selfheal` repo that pulls fresh data from Screener.in via Bright Data Scraper Studio, stores it as JSON, and diffs it against prior state to surface meaningful changes.

The hackathon constraint is that the scraper MUST use a custom Bright Data Scraper Studio collector (already built, ID `c_msvhzc3s2gixuk6k42`). The self-healing capability is native to Scraper Studio — this project demonstrates it by pointing the collector at a deliberately altered page layout.

**Constraints:**
- One-week build, solo developer
- Public repo, no login-gated data
- Must remain explainable end-to-end by the author
- `stock-screeners` repo is NOT to be modified; format compatibility is the integration contract

## Goals / Non-Goals

**Goals:**
- Trigger a Bright Data Scraper Studio collector run and persist results as `data/latest.json`
- Define a canonical JSON schema that is the single source of truth for scraped records
- Diff new results against stored previous state and emit a Markdown change report
- Automate the full loop via GitHub Actions on push to `main`
- Provide a reproducible self-healing demo using a static mirrored page with altered layout
- Produce a clear README suitable for hackathon submission

**Non-Goals:**
- Modifying the `stock-screeners` repo
- Scraping NSE/BSE corporate announcements (future work only)
- Broker API integration or trade execution
- Real-time streaming; batch/scheduled is sufficient
- Production-grade error recovery or SLAs

## Decisions

### Decision 1: Language — Python

**Choice:** Python for all custom scripts (`scraper_client.py`, `diff_engine.py`).

**Rationale:** The existing `stock-screeners` tracker is Python. Keeping the same language makes the data layer immediately readable by the tracker's tooling and by the author. Node.js boilerplate from Bright Data is available but would introduce a second runtime.

**Alternative considered:** Node.js — rejected because it adds a `node_modules` dependency and splits the runtime from the rest of the project.

### Decision 2: Integration lives in `screener-selfheal`, not `stock-screeners`

**Choice:** All new code (scraper client, diff engine, GitHub Actions) lives in `screener-selfheal`. The `stock-screeners` repo is read-only from this project's perspective.

**Rationale:** Keeps `stock-screeners` stable and unmodified. The shared contract is the JSON output schema — either repo's tooling can consume `data/latest.json` or the Markdown change reports. This avoids merge conflicts and keeps the hackathon project self-contained.

**Alternative considered:** Extending `stock-screeners` directly — rejected because it conflates two concerns and modifies an existing working tool.

### Decision 3: Polling, not webhooks, for Bright Data API

**Choice:** `scraper_client.py` calls `/dca/trigger`, then polls `/dca/dataset` on a fixed interval (5 s default, configurable) until status is `ready` or a timeout is reached.

**Rationale:** Bright Data's Scraper Studio API supports webhooks but they require a publicly reachable endpoint. A GitHub Actions runner has no stable inbound URL. Polling is simpler, works in any environment, and is well within rate limits for a one-off scrape job.

**Alternative considered:** Webhook — rejected due to GitHub Actions runner networking constraints.

### Decision 4: Git history as audit log

**Choice:** The Actions workflow commits `data/latest.json` and any change report back to `main` after each successful run, using `[skip ci]` in the commit message to break the loop.

**Rationale:** Zero additional infrastructure required. Git diff between commits gives a visible, timestamped record of every scrape. This is the "audit trail" deliverable for the hackathon.

**Alternative considered:** External storage (S3, Supabase) — rejected as over-engineering for a one-week solo build.

### Decision 5: Self-healing demo via static mirror hosted on GitHub Pages

**Choice:** A static HTML file (`demo/mirror/index.html`) with altered column headers / table structure, hosted via GitHub Pages. The `selfheal-demo.yml` workflow (manual-dispatch only) points the collector at the GitHub Pages URL. The production `scrape-on-merge.yml` workflow always targets the real Screener.in URL.

**Rationale:** The live Screener.in page is unlikely to change mid-week. A controlled static mirror gives a reproducible, demonstrable failure-and-recovery scenario for the demo video. GitHub Pages is free for public repos, requires one setting toggle, and gives a stable public URL that Bright Data's cloud infrastructure can reach — unlike localhost or a CI runner's ephemeral address.

**Alternative considered:** Serving the mirror from a `python3 -m http.server` process inside the GitHub Actions runner — rejected because Bright Data's collector is a cloud service that cannot reach an address local to the runner.

**Setup required:** Enable GitHub Pages in repo Settings → Pages → Source: `main` branch, `/ (root)`. The mirror will be available at `https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html`.

### Decision 6: Change report — append to dated file with per-run headers

**Choice:** One file per calendar day (`data/changes-YYYY-MM-DD.md`). If the scraper runs multiple times in the same day, each run's results are **appended** to the existing file under a `## Run at HH:MM:SS UTC` section header, separated by a horizontal rule.

**Rationale:** Multiple runs per day are likely (manual re-runs, CI retries). Writing separate files per run would scatter a day's changes across `changes-2024-06-15-1.md`, `changes-2024-06-15-2.md`, etc. Appending keeps all of a day's activity readable in one place, matching the advisory/log style of `stock-screeners`. The section header makes individual runs easy to find.

**Alternative considered:** A per-run timestamp filename (`changes-2024-06-15T10-30-00.md`) — rejected because it fragments a day's changes across many files with no natural grouping.

## Risks / Trade-offs

- **Screener.in blocks the scraper** → Mitigation: Bright Data's infrastructure handles IP rotation. The target URL is a public, login-free screen. If blocked, the collector's self-healing / re-prompt mechanism is itself the demo content.
- **Bright Data API schema changes** → Mitigation: Pin to documented `/dca/trigger` and `/dca/dataset` endpoints; add response validation at the client boundary.
- **Repo size growth from committed JSON** → Mitigation: `data/latest.json` is small (< 50 KB for the dividend screen). Not a concern at this scale.
- **GitHub Actions `GITHUB_TOKEN` permissions for committing back** → Mitigation: Use `actions/checkout` with `persist-credentials: true` and `git push` with the default token; grant `contents: write` in workflow permissions block.
- **Self-healing demo is artificial** → Trade-off accepted: This is a hackathon, not production. The demo clearly labels the mirror as a test fixture. The real self-healing mechanism (Scraper Studio's re-prompt flow) is genuine.
- **Diff engine heuristics may produce false positives** → Mitigation: Use a configurable yield-change threshold (default 0.5 pp) and require the field to be non-null before flagging. Document the thresholds in the README.

## Open Questions

_All open questions resolved._
