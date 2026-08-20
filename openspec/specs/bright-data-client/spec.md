# Bright Data Client

## Purpose

The Bright Data client encapsulates all interactions with the Bright Data Collector API, including triggering dataset collection and polling for dataset readiness. It provides a clean interface for the rest of the application to request data without dealing with HTTP-level details or polling mechanics.

## Requirements

### Requirement: poll_until_ready detects dataset readiness via HTTP status code
`poll_until_ready()` SHALL poll `GET /dca/dataset?id={dataset_id}&format=json` and use the HTTP response status code to determine readiness: HTTP 202 means still building (keep polling); HTTP 200 means the dataset is ready (return `dataset_id`).

#### Scenario: Dataset becomes ready after several polls
- **WHEN** the first two poll responses return HTTP 202 and the third returns HTTP 200
- **THEN** `poll_until_ready()` returns the `dataset_id` after exactly three requests

#### Scenario: Dataset is ready immediately on first poll
- **WHEN** the first poll response returns HTTP 200
- **THEN** `poll_until_ready()` returns the `dataset_id` after exactly one request

#### Scenario: Dataset never becomes ready within timeout
- **WHEN** all poll responses return HTTP 202 until the timeout elapses
- **THEN** `poll_until_ready()` raises `TimeoutError` with a message including the dataset ID and elapsed time

#### Scenario: Poll response body is unparseable on consecutive attempts
- **WHEN** the response body cannot be parsed as JSON for more than 2 consecutive polls
- **THEN** `poll_until_ready()` raises an exception rather than looping indefinitely

#### Scenario: Empty body with zero-record dataset
- **WHEN** the collector run completed with zero records and the response body is empty (HTTP 200, 0 bytes)
- **THEN** `poll_until_ready()` treats the 200 status as ready and returns the `dataset_id` without raising

### Requirement: poll_until_ready includes format=json in all polling requests
`poll_until_ready()` SHALL always include `"format": "json"` as a query parameter in every GET request to `/dca/dataset`, so the endpoint returns status JSON (HTTP 202) rather than a raw NDJSON stream.

#### Scenario: Correct query parameter is sent
- **WHEN** `poll_until_ready()` is called with a dataset ID
- **THEN** every outgoing GET request includes `format=json` in the query string
