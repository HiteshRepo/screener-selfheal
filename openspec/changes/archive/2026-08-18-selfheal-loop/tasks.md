## 1. Dependencies and Configuration

- [x] 1.1 Add `openai` to `requirements.txt`
- [x] 1.2 Add `OPENAI_API_KEY=` entry to `.env.example`

## 2. Health Check Module

- [x] 2.1 Create `src/health_check.py` with `HealthStatus` enum (`HEALTHY`, `DEGRADED`, `BROKEN`)
- [x] 2.2 Implement `HealthReport` as a frozen dataclass with `status: HealthStatus` and `reason: str`
- [x] 2.3 Implement `health_check(envelope: dict) -> HealthReport` — check empty records (BROKEN), count mismatch (BROKEN), partial validation failures (DEGRADED), all-invalid (BROKEN), all-valid (HEALTHY)

## 3. Page Analyser Module

- [x] 3.1 Create `src/page_analyser.py` with `analyse_page(target_url: str) -> str`
- [x] 3.2 Implement HTTP fetch using `requests.get`; log a WARNING on non-200 status but continue
- [x] 3.3 Load canonical schema field names from `data/schema.json` and include them in the OpenAI prompt
- [x] 3.4 Call OpenAI SDK (`gpt-4o`) with HTML + schema fields; read `OPENAI_API_KEY` from `os.environ`; raise `ConfigurationError` if absent
- [x] 3.5 Truncate the returned fix description to 900 characters before returning

## 4. Extend BrightDataClient

- [x] 4.1 Add `refactor_template(prompt: str) -> str` — POST to `/dca/collectors/{collector_id}/refactor_template`, return job ID; raise on non-2xx
- [x] 4.2 Add `poll_refactor(job_id: str, timeout: int = 300) -> str` — poll `/dca/collectors/{collector_id}/refactor_template/progress` until `done` or `pending_answer`; raise `TimeoutError` on timeout
- [x] 4.3 Add `approve_refactor(job_id: str) -> None` — POST to `/dca/collectors/{collector_id}/resume_automation_job` with `{"message": true, "auto_save": true}`; raise on non-2xx

## 5. Self-Heal Orchestrator

- [x] 5.1 Create `src/run_selfheal.py` with `argparse` accepting optional `--target-url`
- [x] 5.2 Implement download → health check → early-exit path when `HEALTHY`
- [x] 5.3 Implement full self-heal path: `analyse_page` → `refactor_template` → `poll_refactor` → `approve_refactor` → `trigger_run` → `poll_until_ready` → `download_results` → second `health_check`
- [x] 5.4 Enforce at-most-two cycle limit; exit non-zero if second check is not `HEALTHY`
- [x] 5.5 Log a structured summary before exit: original status, fix prompt sent, recovery status

## 6. GitHub Actions Workflow

- [x] 6.1 Create `.github/workflows/selfheal-loop.yml` with `workflow_dispatch` trigger and optional `target_url` input
- [x] 6.2 Add job steps: checkout, Python setup, install dependencies, run `python src/run_selfheal.py`
- [x] 6.3 Inject secrets `BRIGHT_DATA_API_TOKEN`, `BRIGHT_DATA_COLLECTOR_ID`, `OPENAI_API_KEY`
- [x] 6.4 Add step to commit `data/latest.json` and `data/changes-*.md` back to `main` with `[skip ci]`

## 7. Tests

- [x] 7.1 Create `tests/test_health_check.py` — test healthy envelope, zero records → BROKEN, count mismatch → BROKEN, partial failures → DEGRADED, all failures → BROKEN
- [x] 7.2 Create `tests/test_page_analyser.py` — mock `requests.get` and OpenAI client; verify prompt includes schema fields and HTML; verify 900-char cap is enforced

## 8. Makefile and Documentation

- [x] 8.1 Add `selfheal` target to `Makefile` — runs `python src/run_selfheal.py`
- [x] 8.2 Add `test-health` target — runs `pytest tests/test_health_check.py`
- [x] 8.3 Add `test-analyser` target — runs `pytest tests/test_page_analyser.py`
- [x] 8.4 Add self-heal loop section to `TESTING.md` — local run instructions, required secrets, expected output at each step
