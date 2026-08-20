## 1. Fix src/page_analyser.py

- [x] 1.1 Define `PageFetchError(Exception)` class in `src/page_analyser.py` (above `analyse_page`)
- [x] 1.2 Replace the `logger.warning(...)` block on non-200 (lines 44-46) with `raise PageFetchError(f"GET {target_url} returned HTTP {response.status_code}")`
- [x] 1.3 Verify `response.text` is never read on the non-200 path (raise must come before line 48)

## 2. Update tests/test_page_analyser.py

- [x] 2.1 Add test: `analyse_page()` raises `PageFetchError` when `requests.get` returns HTTP 404 (mock requests.get and OpenAI client — no live calls)
- [x] 2.2 Add test: `analyse_page()` raises `PageFetchError` when `requests.get` returns HTTP 500
- [x] 2.3 Add test: `analyse_page()` calls OpenAI and returns a string ≤ 900 chars when `requests.get` returns HTTP 200
- [x] 2.4 Run `make test` (or `pytest tests/test_page_analyser.py`) and confirm all three tests pass
