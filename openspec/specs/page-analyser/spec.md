# Spec: page-analyser

## Purpose

The `page-analyser` capability is responsible for fetching a target URL and analysing its HTML content via OpenAI GPT-4o, returning a concise analysis string. It guards against non-200 HTTP responses by raising a typed error before any AI call is made.

---

## Requirements

### Requirement: analyse_page raises on non-200 target URL response
`analyse_page()` SHALL raise `PageFetchError` immediately when the HTTP response status code from the target URL is not 200, without reading the response body or calling OpenAI. The exception message MUST include the target URL and the HTTP status code.

#### Scenario: Target URL returns 404
- **WHEN** `requests.get(target_url)` returns HTTP 404
- **THEN** `analyse_page()` raises `PageFetchError` with the URL and status code 404 in the message, and OpenAI is never called

#### Scenario: Target URL returns 500
- **WHEN** `requests.get(target_url)` returns HTTP 500
- **THEN** `analyse_page()` raises `PageFetchError` with the URL and status code 500 in the message, and OpenAI is never called

### Requirement: analyse_page succeeds and returns a string on 200
`analyse_page()` SHALL call OpenAI GPT-4o and return the truncated completion string when the target URL returns HTTP 200.

#### Scenario: Target URL returns 200
- **WHEN** `requests.get(target_url)` returns HTTP 200 with valid HTML
- **THEN** `analyse_page()` calls OpenAI with the HTML, and returns a non-empty string of at most 900 characters
