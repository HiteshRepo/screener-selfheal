# Claude CLI Prompt — Fix poll_until_ready Timeout Bug (Phase 3)

Paste this as your opening prompt to Claude Code (`claude` CLI) inside the `screener-selfheal` project directory. Read the existing codebase before proposing anything — especially `src/scraper_client.py` and `.github/workflows/scrape-on-merge.yml`.

---

## PROMPT

I'm fixing a confirmed bug in an existing project: `https://github.com/HiteshRepo/screener-selfheal`. Read the full codebase before proposing anything. This is a surgical fix — do not refactor unrelated code.

### Context: what already exists

The project has three phases:
- **Phase 1** — Bright Data scraper client, diff engine, schema validation, GitHub Actions
- **Phase 2** — Self-heal loop: health check, page analyser (OpenAI), refactor_template API, run_selfheal.py orchestrator
- **Phase 3 (this session)** — Fix a confirmed API polling bug that causes GHA timeouts

### The Bug (confirmed via live API inspection)

`poll_until_ready()` in `src/scraper_client.py` polls this endpoint:

```
GET https://api.brightdata.com/dca/dataset?id={dataset_id}
```

**Without** the `format=json` parameter. This endpoint behaves differently depending on whether `format=json` is present:

| Request | While building | When done |
|---|---|---|
| `GET /dca/dataset?id=...` | Empty body, HTTP 200 | NDJSON stream, HTTP 200 |
| `GET /dca/dataset?id=...&format=json` | `{"status":"building","message":"..."}` HTTP 202 | Records list, HTTP 200 |

**What actually happens in GHA:**
1. Trigger returns `dataset_id = j_msyltf4p1s7mfnif2r`
2. First poll: `status=collecting` (early, API returns JSON) → continues
3. Second poll: `status=building` → continues
4. Subsequent polls: empty NDJSON body → `response.json()` raises `ValueError` → code treats it as "still warming up" and sleeps 5s → repeats
5. After 300s: `TimeoutError` — GHA job fails

**Confirmed via curl:**
```bash
# Without format=json — returns empty NDJSON (HTTP 200, 0 bytes, content-type: application/jsonl)
curl -H "Authorization: Bearer $TOKEN" "https://api.brightdata.com/dca/dataset?id=j_msyltf4p1s7mfnif2r"
# → empty body

# With format=json — returns status JSON (HTTP 202) while building
curl -H "Authorization: Bearer $TOKEN" "https://api.brightdata.com/dca/dataset?id=j_msyltf4p1s7mfnif2r&format=json"
# → {"status":"building","message":"Dataset is not ready yet, try again in 30s"}
```

The Bright Data dashboard shows the same run completed in ~4s on their side — the scrape finishes quickly, but our client never detects it as ready.

### Root cause summary

`poll_until_ready()` at `scraper_client.py:125` is missing `"format": "json"` in its request params. The correct signal for "ready" is **HTTP 200** when `format=json` is present; HTTP 202 means still building.

### Secondary finding

The collector returned **0 records and 1 failed crawl** for all recent runs (visible in Bright Data dashboard). This means the collector's CSS selectors are broken against the current screener.in HTML — exactly the scenario `run_selfheal.py` is built to fix. The polling bug prevented self-heal from ever running. Once polling is fixed, the self-heal loop should be able to detect and repair this.

### What I need from you in this session

1. **Fix `poll_until_ready()` in `src/scraper_client.py`**:
   - Add `"format": "json"` to the GET request params
   - Change the ready condition from `last_status == "ready"` to HTTP status code check: **202 = still building (keep polling), 200 = ready (return)**
   - When HTTP 200 is received, do NOT try to parse a `status` field — the body is the actual records list; just return the `dataset_id`
   - Keep `ValueError` handling for truly empty bodies (edge case), but log a warning and treat it as still pending for at most 2 consecutive occurrences before raising, so we don't spin forever on a malformed response
   - Do not change the function signature or return type

2. **Fix `download_results()` in `src/scraper_client.py`**:
   - Verify it already uses `format=json` (it does) — no change needed if so
   - If not, add it

3. **Update `tests/test_scraper_client.py`**:
   - Add a test: poll returns HTTP 202 twice then HTTP 200 → function returns after 3 calls
   - Add a test: poll returns HTTP 200 immediately → function returns after 1 call
   - Add a test: poll always returns HTTP 202 beyond timeout → `TimeoutError` raised
   - Add a test: poll returns empty body (ValueError on json()) repeatedly → eventually raises, does not loop forever
   - Do NOT add live API calls — mock `requests.Session.get`

4. **Do not change**:
   - `run_selfheal.py`, `run_scrape.py`, `health_check.py`, `page_analyser.py`, `diff_engine.py`, `schema.py`
   - GitHub Actions workflows
   - Any test file other than `test_scraper_client.py`
   - The `Makefile` or `TESTING.md`

### Hard constraints

- This is a one-file fix (`src/scraper_client.py`) plus one test file update — do not broaden scope
- Do not change any other polling logic (`poll_refactor` uses a different endpoint with different status semantics — leave it alone)
- Keep the existing logging format: `dataset_id=%s status=%s elapsed=%.0fs` — update the `status` value logged to reflect the HTTP status code or parsed body, whichever is available
- No new dependencies

### Confirm before writing code

- Restate the fix in 3 bullets
- Confirm `download_results()` already uses `format=json` (read the file first)
- Flag any risk: if `format=json` changes the response shape in a way that breaks `download_results()`, call it out before touching anything

---

## Before you run this

- [x] Bug confirmed via live `curl` against the Bright Data API
- [x] Root cause identified: missing `format=json` in `poll_until_ready()` request params
- [x] Secondary finding confirmed: collector returning 0 records / failed crawls (broken selectors — separate issue, fixed by running `make selfheal` once polling is fixed)
- [x] GHA run that failed: `https://github.com/HiteshRepo/screener-selfheal/actions/runs/32133965127/job/95700974220`
- [x] Affected dataset ID: `j_msyltf4p1s7mfnif2r`
