## Context

The Phase 1 screener-selfheal project can trigger a Bright Data collector, poll for completion, download results into `data/latest.json`, validate records against a JSON Schema, and compare snapshots. It has no recovery path when the collector returns broken or empty data — the only option today is manual intervention.

Phase 2 adds an automated recovery loop. The key external integration is Bright Data's AI Flow API (`refactor_template` → `poll_refactor` → `resume_automation_job`), which accepts a natural-language prompt and rewrites the collector's JavaScript internally. OpenAI (`gpt-4o`) bridges the gap between a broken HTML page and that prompt: it receives the raw HTML and the canonical schema fields and returns a concise description of what CSS selectors or structural elements map to each field.

The existing codebase uses: `requests` for HTTP, `dataclasses` for structured return types, `logging` (not `print`), and type annotations on all functions. New code follows the same conventions.

## Goals / Non-Goals

**Goals:**
- Automatically detect when a scrape returns degraded or broken results (zero valid records, count mismatch, or schema failures).
- Use OpenAI to diagnose DOM changes from raw HTML — no Python-side HTML parsing.
- Drive Bright Data's AI Flow API to rewrite the collector from a natural-language prompt.
- Run the repair cycle **at most twice** — one attempt and one verification — then surface a clear error if recovery fails.
- Keep the `data/latest.json` envelope format unchanged; `run_selfheal.py` writes to the same file as `run_scrape.py`.
- Remain in the same Python repo with no new infrastructure.

**Non-Goals:**
- Implementing a retry spiral or indefinite polling loop.
- Adding Playwright, Selenium, or BeautifulSoup — `requests` only for page fetching.
- Scattering LLM calls across modules — the OpenAI API call is isolated in `src/page_analyser.py`.
- Replacing Bright Data's passive self-healing — this is a separate, actively-driven layer.

## Decisions

### 1. Three-layer separation: health check → page analyser → orchestrator

**Decision:** Health detection, LLM diagnosis, and API orchestration live in three separate modules (`health_check.py`, `page_analyser.py`, `run_selfheal.py`), not in one monolithic script.

**Rationale:** Each layer has a single responsibility and a well-defined interface. `health_check.py` is pure data inspection (no I/O side effects); `page_analyser.py` is the only module that calls OpenAI; `run_selfheal.py` sequences the steps. This makes unit testing straightforward — each module can be tested with mocks at its boundary.

**Alternative considered:** One fat `run_selfheal.py` that does everything. Rejected because it cannot be unit-tested at the module level and mixes I/O concerns.

### 2. OpenAI API call lives exclusively in `page_analyser.py`

**Decision:** The OpenAI SDK import and API call are contained in `page_analyser.py`. No other module touches the OpenAI client.

**Rationale:** Isolating the LLM dependency makes it easy to mock in tests — only `test_page_analyser.py` needs to patch the OpenAI client. Keeping it in one place also makes swapping models trivial.

### 3. `BrightDataClient` extended with three new methods (not a subclass)

**Decision:** Add `refactor_template()`, `poll_refactor()`, and `approve_refactor()` as methods on the existing `BrightDataClient` class rather than creating a subclass or a separate client.

**Rationale:** The AI Flow API shares the same base URL, auth header, and session. Extending the existing class avoids duplicating auth setup and keeps the collector ID in one place. Existing method signatures are unchanged.

**Alternative considered:** A separate `BrightDataAIFlowClient`. Rejected as unnecessary abstraction for three methods that share all configuration with the existing client.

### 4. `HealthReport` as a frozen dataclass with an enum status

**Decision:** `HealthReport` is a `@dataclass(frozen=True)` with a `HealthStatus` enum (`HEALTHY`, `DEGRADED`, `BROKEN`) and a `reason: str` field.

**Rationale:** Matches the project's existing pattern of using dataclasses for structured return types. Frozen ensures callers cannot accidentally mutate the result. The enum makes exhaustive matching possible in the orchestrator.

### 5. Fix description capped at 900 chars, validated before sending

**Decision:** `page_analyser.py` enforces a 900-character cap on the returned fix description (truncating if the model returns more) before it is passed to `refactor_template`.

**Rationale:** The Bright Data API has a 1000-char limit on the prompt field. A 900-char cap leaves 100 chars of safety margin and is validated in `test_page_analyser.py`.

### 6. At-most-two iterations enforced in the orchestrator

**Decision:** `run_selfheal.py` runs the loop at most twice — initial download+check, and if broken: fix attempt + re-download + re-check. If the second check still fails, the script exits with a non-zero code and a structured error summary. There is no retry spiral.

**Rationale:** The prompt file requires this. Unbounded retries risk burning Bright Data API quota and OpenAI tokens on a problem that may require human intervention.

### 7. `OPENAI_API_KEY` follows the existing secret pattern

**Decision:** The key is read from `os.environ`, added to `.env.example`, and injected as a GitHub Actions secret — identical to how `BRIGHT_DATA_API_TOKEN` is handled.

**Rationale:** Consistency. The project already has a clear secret-management pattern; no reason to deviate.

## Risks / Trade-offs

**[Risk] `refactor_template` endpoint not available on the Bright Data plan** → The orchestrator wraps the POST in a try/except that catches HTTP 403/404 and exits with a clear error message: "AI Flow API unavailable on this plan — manual repair required." No silent failure.

**[Risk] OpenAI returns a fix description that does not produce a working collector rewrite** → The second health check catches this. The script exits with a non-zero code and logs the fix prompt that was sent, enabling manual review.

**[Risk] `poll_refactor` hangs if Bright Data's internal rewrite never reaches `done` or `pending_answer`** → `poll_refactor` has a configurable `timeout` (default 300 s) and raises `TimeoutError` if exceeded. The orchestrator propagates this as a fatal error.

**[Risk] Page fetch returns non-HTML (redirect to login, CAPTCHA, etc.)** → `page_analyser.py` passes the raw response body to OpenAI regardless; the model will surface the anomaly in the fix description. The orchestrator logs a warning if the HTTP status is not 200.

**[Trade-off] No Python-side HTML parsing** → The fix description quality is entirely dependent on the OpenAI model's ability to read raw HTML. This keeps the dependency surface minimal (no BeautifulSoup) but means the prompt must include clear schema context for the model to produce a useful description.

## Migration Plan

1. Merge Phase 2 branch to `main` — no schema changes, no breaking changes to existing entry points.
2. Add `OPENAI_API_KEY` as a GitHub Actions secret before running the new workflow.
3. Add `OPENAI_API_KEY` to local `.env` for local runs.
4. Verify Bright Data plan supports AI Flow API endpoints — if not, the orchestrator will exit with a clear error on first invocation.
5. Run `make test-health && make test-analyser` to verify new tests pass.
6. Run `make selfheal` locally against the mirror page to validate end-to-end.

## Open Questions

- **Bright Data plan support**: The `refactor_template` endpoint is not GA-confirmed. This must be validated against the account before relying on the selfheal workflow in production.
- **`poll_refactor` response shape**: The `progress` endpoint is assumed to return a JSON body with a `status` field containing `done`, `pending_answer`, or an in-progress value. The exact shape should be confirmed against Bright Data's documentation or a test call before implementation.
