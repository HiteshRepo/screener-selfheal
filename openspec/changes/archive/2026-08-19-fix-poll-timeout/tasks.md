## 1. Fix poll_until_ready in scraper_client.py

- [x] 1.1 Add `"format": "json"` to the GET request params in `poll_until_ready()` (`scraper_client.py:125`)
- [x] 1.2 Replace the `last_status == "ready"` body-parsing check with an HTTP status code check: HTTP 200 → return `dataset_id`; HTTP 202 → keep polling
- [x] 1.3 Update the log line to read `status` from the 202 response body when available, log `http_200_ready` on 200
- [x] 1.4 Add a consecutive-ValueError counter (max 2) — reset on any successful parse; raise after 2 consecutive failures instead of looping indefinitely
- [x] 1.5 Remove the comment referencing "empty body = warm-up" since it no longer applies with `format=json`

## 2. Update tests/test_scraper_client.py

- [x] 2.1 Add test: poll returns HTTP 202 twice then HTTP 200 → function returns `dataset_id` after exactly 3 requests
- [x] 2.2 Add test: poll returns HTTP 200 immediately → function returns after 1 request
- [x] 2.3 Add test: poll always returns HTTP 202 beyond timeout → `TimeoutError` raised with dataset ID in message
- [x] 2.4 Add test: poll returns unparseable body for 3 consecutive responses → raises (not infinite loop)
- [x] 2.5 Add test: verify every mock GET call includes `format=json` in params
- [x] 2.6 Run `make test-scraper` and confirm all tests pass
