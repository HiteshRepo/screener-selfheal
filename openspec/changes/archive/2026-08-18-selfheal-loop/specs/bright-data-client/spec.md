## ADDED Requirements

### Requirement: refactor_template sends fix prompt and returns job ID
`BrightDataClient.refactor_template(prompt: str) -> str` SHALL POST to `/dca/collectors/{collector_id}/refactor_template` with body `{"prompt": prompt}` and return the job ID from the response.

#### Scenario: Successful refactor trigger
- **WHEN** `refactor_template("fix the dividend column selector")` is called
- **THEN** the client POSTs to the correct endpoint and returns the job ID string from the response body

#### Scenario: Non-2xx response raises an error
- **WHEN** the API returns HTTP 403 or 404
- **THEN** `refactor_template` raises an exception with a message that includes the HTTP status code and response body

### Requirement: poll_refactor polls until done or pending_answer
`BrightDataClient.poll_refactor(job_id: str, timeout: int = 300) -> str` SHALL GET `/dca/collectors/{collector_id}/refactor_template/progress`, poll at a fixed interval, and return the terminal status string (`"done"` or `"pending_answer"`) when reached.

#### Scenario: Status reaches done within timeout
- **WHEN** the progress endpoint returns `{"status": "done"}` on the third poll
- **THEN** `poll_refactor` returns `"done"`

#### Scenario: Timeout exceeded raises TimeoutError
- **WHEN** the progress endpoint never returns `"done"` or `"pending_answer"` within `timeout` seconds
- **THEN** `poll_refactor` raises `TimeoutError` with a message naming the job ID and elapsed time

### Requirement: approve_refactor approves the rewrite
`BrightDataClient.approve_refactor(job_id: str) -> None` SHALL POST to `/dca/collectors/{collector_id}/resume_automation_job` with body `{"message": true, "auto_save": true}`.

#### Scenario: Successful approval
- **WHEN** `approve_refactor(job_id)` is called and the API returns 2xx
- **THEN** the method returns without error

#### Scenario: Non-2xx approval response raises an error
- **WHEN** the API returns HTTP 500
- **THEN** `approve_refactor` raises an exception with the HTTP status and response body

### Requirement: Existing BrightDataClient methods are unchanged
The new methods SHALL be added to `BrightDataClient` without altering the signatures or behaviour of `trigger_run`, `poll_until_ready`, or `download_results`.

#### Scenario: Existing call signatures preserved
- **WHEN** code calls `client.trigger_run()` or `client.poll_until_ready(dataset_id)` after the Phase 2 changes
- **THEN** these methods behave identically to their Phase 1 implementations
