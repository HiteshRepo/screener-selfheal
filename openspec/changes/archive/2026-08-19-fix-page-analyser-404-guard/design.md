## Context

`analyse_page()` in `src/page_analyser.py` fetches a target URL and passes its HTML to OpenAI GPT-4o. The current non-200 path logs a warning at line 44 but falls through — `response.text` is still read and passed to OpenAI regardless of status code. When the URL returns 404, GPT-4o sees a "Page Not Found" HTML document and generates a meaningless prompt, which causes Bright Data's `refactor_template` API to return HTTP 500.

`run_selfheal.py` already wraps the call to `analyse_page()` in a broad `except Exception`, so raising from inside `analyse_page()` is the cleanest fix — no changes needed upstream.

## Goals / Non-Goals

**Goals:**
- Raise immediately in `analyse_page()` when the target URL returns a non-200 HTTP status
- Include URL and status code in the exception message for actionable logs
- Add a named custom exception (`PageFetchError`) so callers can catch it specifically if needed
- Cover the new raise path with tests (404, 500, 200-success)

**Non-Goals:**
- Retry logic on non-200 (not requested, adds complexity)
- Changes to `run_selfheal.py`, `scraper_client.py`, workflows, or the Makefile
- New dependencies

## Decisions

**Use a custom `PageFetchError` instead of bare `RuntimeError`**
Rationale: a named exception lets callers (current or future) distinguish a fetch failure from other `RuntimeError`s without parsing message strings. Defined in the same file — no new module needed.

**Raise immediately, do not read `response.text`**
Rationale: reading the body after a non-200 wastes memory and risks the fall-through bug recurring if the code is refactored. Raising before `response.text` is accessed makes the guard explicit.

**Exception message format: `PageFetchError: GET <url> returned HTTP <status>`**
Rationale: URL and status are the two actionable fields. Matches the existing warning log format so log correlation is straightforward.

## Risks / Trade-offs

[Risk] `run_selfheal.py` catches all exceptions — a new `PageFetchError` will be caught by the existing `except Exception` block → No action needed; self-heal will log and exit with `recovery_status=failed`, which is the correct outcome.

[Risk] Tests mock `requests.get` — if the real URL changes again, tests still pass → Acceptable trade-off; the URL correctness is validated by the scrape workflow, not the analyser tests.
