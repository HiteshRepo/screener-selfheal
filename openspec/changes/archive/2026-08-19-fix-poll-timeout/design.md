## Context

`BrightDataClient.poll_until_ready()` in `src/scraper_client.py` is the polling loop that waits for a triggered dataset to become available for download. It calls `GET /dca/dataset?id={dataset_id}` (no `format=json`), expecting the response to be a JSON object with a `status` field.

The Bright Data dataset endpoint has two distinct modes depending on whether `format=json` is present:

- **Without `format=json`**: Returns the dataset as a raw NDJSON stream immediately when available; returns an empty body (HTTP 200, 0 bytes) when the dataset exists but has zero records.
- **With `format=json`**: Returns `{"status":"building","message":"..."}` with HTTP 202 while processing; returns the records list with HTTP 200 when ready.

The current code expects the `status` field but polls the wrong endpoint variant. When the dataset completes with zero records (collector broken), the body is empty, `response.json()` raises `ValueError`, and the existing `ValueError` handler treats it as "still warming up" — sleeping and retrying until the 300s timeout expires. This was confirmed via live `curl` against dataset `j_msyltf4p1s7mfnif2r`.

## Goals / Non-Goals

**Goals:**
- Fix `poll_until_ready()` to use `format=json` and detect readiness via HTTP status code (202 → keep polling, 200 → ready)
- Ensure zero-record completions are detected as ready immediately, not spun for 300s
- Add tests covering the corrected polling flow
- Keep the fix minimal — one method, one test file

**Non-Goals:**
- Fixing the broken collector CSS selectors (separate concern — `make selfheal` handles that once polling works)
- Changing `poll_refactor()`, `download_results()`, or any other method
- Changing GHA workflows or documentation

## Decisions

### Decision 1: Use HTTP status code as the ready signal (not response body parsing)

With `format=json`, Bright Data returns HTTP 202 while building and HTTP 200 when ready. The 200 body is the records list (a JSON array), not a status object. Using the HTTP status code is the correct and stable signal.

**Alternative considered:** Parse the body and check `if isinstance(data, list)` to detect the records response. Rejected — more fragile than checking the status code and depends on the body shape being a list, which may not hold for all edge cases.

### Decision 2: Treat consecutive `ValueError` on json() as a terminal error, not infinite retry

If `format=json` is present and the body is somehow unparseable, that is unexpected. Allow at most 2 consecutive parse failures before raising, to prevent silent infinite loops. Reset the counter on any successful parse.

**Alternative considered:** Remove ValueError handling entirely now that `format=json` is used. Rejected — defensive; Bright Data could return an empty body for any transient reason, and one retry is cheap.

### Decision 3: Log the HTTP status code when `format=json` returns 202

The existing log format is `dataset_id=%s status=%s elapsed=%.0fs`. Preserve this but populate `status` from the response body's `status` field when available (202 responses include it), and log `http_200_ready` when 200 is received.

## Risks / Trade-offs

- **Risk: `format=json` changes download behaviour** → `download_results()` already uses `format=json` and expects a records list on 200; adding it to `poll_until_ready()` only affects the polling response shape, not the download. No conflict.
- **Risk: Bright Data changes HTTP status codes** → Unlikely for a stable API; the 202/200 contract is standard REST semantics. The `message` field in the 202 body ("try again in 30s") further confirms intent.
- **Trade-off: Removing the "warm-up" empty-body retry** → The original comment said empty body = warm-up. With `format=json` this no longer applies; 202 is the warm-up signal. The only scenario where we'd still get an empty body is a genuine API error, which should be surfaced, not silently retried.
