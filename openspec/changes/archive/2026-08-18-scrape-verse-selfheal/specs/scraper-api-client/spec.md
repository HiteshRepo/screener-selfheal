## ADDED Requirements

### Requirement: Trigger collector run
The client SHALL call the Bright Data `/dca/trigger` endpoint with the configured collector ID and return a dataset ID for subsequent polling.

#### Scenario: Successful trigger
- **WHEN** `BRIGHT_DATA_API_TOKEN` and `BRIGHT_DATA_COLLECTOR_ID` are set and the API is reachable
- **THEN** the client returns a non-empty dataset ID string and logs the trigger timestamp

#### Scenario: Missing credentials
- **WHEN** either `BRIGHT_DATA_API_TOKEN` or `BRIGHT_DATA_COLLECTOR_ID` is absent from the environment
- **THEN** the client raises a `ConfigurationError` with a descriptive message before making any network call

#### Scenario: API returns non-2xx on trigger
- **WHEN** the `/dca/trigger` endpoint returns a 4xx or 5xx response
- **THEN** the client raises a `TriggerError` containing the HTTP status code and response body

### Requirement: Poll until ready
The client SHALL poll the `/dca/dataset` endpoint using the dataset ID at a configurable interval until the status is `ready`, or until a configurable timeout is exceeded.

#### Scenario: Dataset becomes ready within timeout
- **WHEN** the dataset status transitions to `ready` before the timeout
- **THEN** the client returns the dataset ID and stops polling

#### Scenario: Timeout exceeded before ready
- **WHEN** the dataset has not reached `ready` status within the configured timeout (default 300 s)
- **THEN** the client raises a `TimeoutError` with the elapsed time and last observed status

#### Scenario: Configurable poll interval
- **WHEN** the caller provides a `poll_interval` argument (in seconds)
- **THEN** the client waits exactly that many seconds between poll requests

### Requirement: Download and persist results
The client SHALL download the completed dataset and write it to a configurable output path (default `data/latest.json`) as a JSON array, one object per scraped company record.

#### Scenario: Successful download
- **WHEN** the dataset status is `ready`
- **THEN** the client writes valid JSON to the output path and returns the record count

#### Scenario: Output directory does not exist
- **WHEN** the output path's parent directory does not exist
- **THEN** the client creates the directory before writing

#### Scenario: Empty dataset
- **WHEN** the API returns an empty result set
- **THEN** the client writes an empty JSON array `[]` and logs a warning

### Requirement: Rotate previous snapshot
Before overwriting `data/latest.json`, the client SHALL copy the existing file to `data/previous.json` to enable diffing.

#### Scenario: Previous snapshot exists
- **WHEN** `data/latest.json` already exists before a new download
- **THEN** the client copies it to `data/previous.json` before writing new results

#### Scenario: No prior snapshot
- **WHEN** `data/latest.json` does not exist
- **THEN** the client skips the copy step and proceeds to write new results directly
