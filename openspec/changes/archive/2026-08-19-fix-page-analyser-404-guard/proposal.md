## Why

`analyse_page()` in `src/page_analyser.py` fetches the target URL and passes its HTML to OpenAI GPT-4o for analysis. When the target URL returns a non-200 response (e.g. 404), the function logs a warning but continues — passing the error page HTML to OpenAI, which generates a useless fix prompt that causes Bright Data's `refactor_template` API to return HTTP 500. This was confirmed in GHA run `32140011281`.

## What Changes

- Replace the `logger.warning(...)` on non-200 in `analyse_page()` with a `raise` that includes the URL and HTTP status code
- Introduce a lightweight custom exception `PageFetchError` (defined in the same file) for clarity
- Add tests covering the raise-on-404, raise-on-500, and success-on-200 cases

## Capabilities

### New Capabilities
- `page-analyser`: Guards `analyse_page()` against non-200 target URL responses by raising `PageFetchError` immediately, preventing garbage HTML from reaching OpenAI

### Modified Capabilities
<!-- No existing spec-level requirements are changing -->

## Impact

- `src/page_analyser.py`: two-line change — replace warning with raise
- `tests/test_page_analyser.py`: new or updated test file (3 tests added)
- `src/run_selfheal.py`: no change — already catches all exceptions from `analyse_page()` with broad `except Exception`
- No new dependencies
