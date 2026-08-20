# Claude CLI Prompt — Guard page_analyser Against Non-200 Target URL

Paste this as your opening prompt to Claude Code (`claude` CLI) inside the `screener-selfheal` project directory. Read the existing codebase before proposing anything — especially `src/page_analyser.py` and `tests/test_page_analyser.py` (if it exists).

---

## PROMPT

I'm fixing a confirmed bug in an existing project: `https://github.com/HiteshRepo/screener-selfheal`. Read the full codebase before proposing anything. This is a surgical fix — do not refactor unrelated code.

### Context: what already exists

The project has three phases:
- **Phase 1** — Bright Data scraper client, diff engine, schema validation, GitHub Actions
- **Phase 2** — Self-heal loop: health check, page analyser (OpenAI), refactor_template API, run_selfheal.py orchestrator
- **Phase 3** — Fixed polling bug in `poll_until_ready()` (already done)
- **Phase 4 (this session)** — Guard `page_analyser.py` against non-200 responses from the target URL

### The Bug (confirmed via live GHA run)

`analyse_page()` in `src/page_analyser.py` fetches the target URL and passes its HTML to OpenAI GPT-4o for analysis. When the target URL returns a non-200 response (e.g. 404), the current code logs a warning but continues — passing the error page HTML to OpenAI.

**What actually happened in GHA run `32140011281`:**
1. Self-heal was triggered because scrape returned 0 records
2. `analyse_page()` fetched `https://www.screener.in/screens/dividend-yield/` → got HTTP 404
3. Logged `WARNING: Non-200 response fetching ...: status=404` but continued
4. Passed the 404 HTML to OpenAI → GPT-4o generated a generic/useless fix prompt about a "404 Page Not Found" page
5. That garbage prompt was sent to Bright Data's `refactor_template` API → HTTP 500: `sprintf invalid format %j`
6. Self-heal failed with `recovery_status=failed`

**The fix prompt GPT-4o generated (from logs):**
> "The HTML content you've provided is a '404 Page Not Found' response... there's no actual data related to companies or financials present in this HTML document..."

This is a meaningless prompt that caused Bright Data's API to error.

### Root cause summary

`analyse_page()` in `src/page_analyser.py` treats any non-200 HTTP response as a warning, not an error. It should raise immediately when the target URL returns non-200, so `run_selfheal.py` can catch it and fail with a clear message instead of sending garbage to downstream APIs.

### What I need from you in this session

1. **Fix `analyse_page()` in `src/page_analyser.py`**:
   - Replace the `logger.warning(...)` on non-200 with a `raise` — raise a descriptive exception (e.g. `RuntimeError` or a new `PageFetchError`) that includes the URL and status code
   - Do not continue to OpenAI when the fetch fails
   - Keep the rest of the function unchanged

2. **Update `tests/test_page_analyser.py`** (or create it if it doesn't exist):
   - Add a test: `analyse_page()` raises when target URL returns 404
   - Add a test: `analyse_page()` raises when target URL returns 500
   - Add a test: `analyse_page()` calls OpenAI and returns a string when target URL returns 200
   - Mock both `requests.get` and the OpenAI client — no live API calls

3. **Do not change**:
   - `run_selfheal.py` — it already catches all exceptions from `analyse_page()` with a broad `except Exception`
   - `scraper_client.py`, `health_check.py`, `diff_engine.py`, `schema.py`, `run_scrape.py`
   - GitHub Actions workflows
   - The `Makefile`

### Hard constraints

- One-file fix (`src/page_analyser.py`) plus test file — do not broaden scope
- No new dependencies — use built-in exceptions or a simple custom exception class defined in the same file
- The exception message must include the URL and the HTTP status code so logs are actionable

### Confirm before writing code

- Restate the fix in 2 bullets
- Show the current non-200 handling code (read the file first)
- Confirm `run_selfheal.py` already catches exceptions from `analyse_page()` — if not, flag it

---

## Before you run this

- [x] Bug confirmed via GHA run logs: `https://github.com/HiteshRepo/screener-selfheal/actions/runs/32140011281`
- [x] Root cause: `analyse_page()` logs warning on non-200 but continues, passing 404 HTML to OpenAI
- [x] Downstream effect confirmed: garbage fix prompt → Bright Data HTTP 500
- [x] `run_selfheal.py` already has broad `except Exception` around `analyse_page()` — raising will be caught cleanly
