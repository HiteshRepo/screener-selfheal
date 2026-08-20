# Claude CLI Prompt — Self-Healing Loop (Phase 2)

Paste this as your opening prompt to Claude Code (`claude` CLI) inside the `screener-selfheal` project directory. Fill in the `[bracketed]` spots before running it. This builds on top of the scraper already built in Phase 1 — read the existing codebase before proposing anything.

---

## PROMPT

I'm extending an existing project: `https://github.com/HiteshRepo/screener-selfheal`. Read the full codebase before proposing anything — especially `src/scraper_client.py`, `src/schema.py`, `src/diff_engine.py`, and the existing GitHub Actions workflows. This phase adds a self-healing loop that we own and control, rather than relying on Bright Data's built-in recovery.

### Context: what already exists

Phase 1 built:
- `BrightDataClient` — trigger a Bright Data Scraper Studio collector, poll until ready, download results as a JSON envelope to `data/latest.json`
- `DiffEngine` — compare two snapshots, classify tickers as ENTERED / EXITED / CHANGED / UNCHANGED, write a dated Markdown report
- `validate_record()` — JSON Schema (Draft 7) validation for every scraped record
- GitHub Actions: `scrape-on-merge.yml` (auto-scrape on push), `selfheal-demo.yml` (manual dispatch against a mirror page)
- A static mirror page at `demo/mirror/index.html` with deliberately altered HTML structure (changed column headers, extra wrapping `<div>`) deployed on GitHub Pages

The collector (`c_msvhzc3s2gixuk6k42`) already exists in Bright Data Scraper Studio. We do not recreate it.

### What we're building in Phase 2

A **self-healing loop we own** — when a scrape returns broken/empty results, we:
1. Detect the failure ourselves (result quality checks)
2. Fetch the live page HTML and use an LLM (Claude API) to identify what changed in the DOM
3. Generate a concise natural-language fix description
4. Push that description to Bright Data's `refactor_template` API to rewrite the collector's script
5. Approve the rewrite programmatically
6. Re-trigger the collector and verify recovery

This is distinct from Bright Data's passive self-healing — we are actively driving the repair cycle in code, triggered by our own failure detection.

### Bright Data AI Flow API (already researched — do not re-research)

The following endpoints are confirmed and documented:

| Step | Method | Path |
|---|---|---|
| Trigger self-heal | POST | `/dca/collectors/{collector_id}/refactor_template` |
| Poll progress | GET | `/dca/collectors/{collector_id}/refactor_template/progress` |
| Approve / reject | POST | `/dca/collectors/{collector_id}/resume_automation_job` |

- `refactor_template` body: `{"prompt": "<natural language fix, max 1000 chars>", "custom_input": [<optional sample inputs>]}`
- `resume_automation_job` body: `{"message": true, "auto_save": true}` to approve
- The collector's JavaScript source is not readable or writable via API — the only update vector is the natural-language prompt; Bright Data's AI rewrites the script internally

### What I need from you in this session

1. **Propose the architecture first** — new modules, data flow, where the LLM call fits, how this integrates with the existing `BrightDataClient` and GitHub Actions — before writing any code. Keep it simple: this runs in the same repo, same Python stack, no new infrastructure.

2. **Failure detection module** (`src/health_check.py`):
   - Inspect a downloaded envelope: empty `records`, `record_count` mismatch, or records that fail `validate_record()`
   - Return a structured `HealthReport` (healthy / degraded / broken) with a failure reason string
   - Degraded = some records invalid; Broken = zero valid records

3. **Page analyser** (`src/page_analyser.py`):
   - Fetch the target page HTML (use `requests`, no headless browser)
   - Call the Claude API (Anthropic SDK, `claude-sonnet-4-6` model) with the fetched HTML and the canonical schema fields as context
   - Ask Claude to identify which CSS selectors or structural elements look like they map to each required field
   - Return a concise fix description (≤900 chars) suitable for the `refactor_template` prompt

4. **Extend `BrightDataClient`** (`src/scraper_client.py`):
   - Add `refactor_template(prompt: str) -> str` — POST to the refactor endpoint, return job ID
   - Add `poll_refactor(job_id: str, timeout: int = 300) -> str` — poll progress until `done` or `pending_answer`; raise `TimeoutError` on timeout
   - Add `approve_refactor(job_id: str) -> None` — POST to `resume_automation_job` with `auto_save: true`

5. **Self-heal orchestrator** (`src/run_selfheal.py`):
   - CLI entry point wiring: `download → health_check → page_analyser → refactor_template → poll_refactor → approve_refactor → re-trigger → poll_until_ready → download → health_check`
   - If health check passes on first download: exit early with a "healthy" message, no refactor needed
   - If refactor is attempted but second health check still fails: exit with a clear error, do not loop indefinitely
   - Print a structured summary at the end: original status, fix prompt sent, recovery status

6. **GitHub Actions workflow** (`.github/workflows/selfheal-loop.yml`):
   - Trigger: `workflow_dispatch` with an optional `target_url` input (defaults to the live Screener.in screen)
   - Inject secrets: `BRIGHT_DATA_API_TOKEN`, `BRIGHT_DATA_COLLECTOR_ID`, `ANTHROPIC_API_KEY`
   - Run: `python src/run_selfheal.py`
   - Commit results (`data/latest.json`, today's `data/changes-*.md`) back to `main` with `[skip ci]`

7. **Tests** (`tests/test_health_check.py`, `tests/test_page_analyser.py`):
   - `test_health_check.py`: healthy envelope passes, zero records → broken, schema failures → degraded, count mismatch → broken
   - `test_page_analyser.py`: mock the Claude API response and the `requests.get` call; verify the prompt construction includes the schema fields and fetched HTML; verify output is ≤900 chars
   - Do NOT add live API calls in tests — mock both `requests.get` and the Anthropic client

8. **Update `Makefile`** — add targets: `selfheal` (run `src/run_selfheal.py`), `test-health` (run `tests/test_health_check.py`), `test-analyser` (run `tests/test_page_analyser.py`)

9. **Update `TESTING.md`** — add a section for the self-heal loop: how to run locally, what secrets are needed, expected output at each step

### Hard constraints

- Do not add a new scraping library (Playwright, Selenium, BeautifulSoup) — use `requests` only for page fetching; the HTML parsing for selector analysis is done by Claude, not by Python code
- Keep the Claude API call in `page_analyser.py` only — do not scatter LLM calls across modules
- The self-heal loop runs **at most twice** (one attempt + one verification) — no retry spiral
- All new secrets (`ANTHROPIC_API_KEY`) follow the same pattern as existing ones: environment variable, `.env.example` entry, GitHub Actions secret — never hardcoded
- Maintain the existing `data/` envelope format — `run_selfheal.py` writes to the same `data/latest.json` that `run_scrape.py` writes to
- Follow existing code style: dataclasses for structured return types, `logging` not `print`, type annotations on all function signatures

### What I need confirmed before you write code

- Architecture proposal (5–8 bullets): new files, data flow, where Claude API fits
- Confirm the Claude model to use for page analysis: `claude-sonnet-4-6` unless you have a reason to suggest otherwise
- Flag any risk: the `refactor_template` API is not GA-confirmed — if it turns out to be unavailable on our plan, what is the fallback?

Start by restating the architecture plan and flagging any risks before touching any files.

---

## Before you run this

- [x] Phase 1 complete: scraper, diff engine, schema validation, GitHub Actions, tests all merged to `main`
- [x] Collector ID confirmed: `c_msvhzc3s2gixuk6k42`
- [ ] `ANTHROPIC_API_KEY` added as a GitHub Actions secret (Settings → Secrets and variables → Actions)
- [ ] `ANTHROPIC_API_KEY` added to local `.env` for local runs
- [ ] Confirmed Bright Data plan supports AI Flow API (`refactor_template` endpoint) — check under your account's API access or contact Bright Data support
