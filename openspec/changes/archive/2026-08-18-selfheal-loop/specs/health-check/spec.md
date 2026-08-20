## ADDED Requirements

### Requirement: Classify envelope as healthy
The system SHALL inspect a downloaded scrape envelope and return `HealthStatus.HEALTHY` when `record_count` in `meta` matches the length of `records`, all records pass `validate_record()`, and `records` is non-empty.

#### Scenario: All records valid and count matches
- **WHEN** the envelope contains `record_count: 3` and three records that all pass schema validation
- **THEN** `health_check(envelope)` returns a `HealthReport` with `status=HealthStatus.HEALTHY` and an empty `reason`

### Requirement: Classify envelope as broken on zero records
The system SHALL return `HealthStatus.BROKEN` with a reason string when `records` is an empty list.

#### Scenario: Empty records list
- **WHEN** the envelope contains `records: []` and `record_count: 0`
- **THEN** `health_check(envelope)` returns `HealthReport(status=HealthStatus.BROKEN, reason="No records returned")`

### Requirement: Classify envelope as broken on record_count mismatch
The system SHALL return `HealthStatus.BROKEN` when the `record_count` field in `meta` does not match the actual length of the `records` list.

#### Scenario: Count greater than actual records
- **WHEN** the envelope declares `record_count: 5` but `records` contains only 2 entries
- **THEN** `health_check(envelope)` returns `HealthReport(status=HealthStatus.BROKEN, reason=...)` with a reason that mentions the mismatch

### Requirement: Classify envelope as degraded on partial schema failures
The system SHALL return `HealthStatus.DEGRADED` when at least one record passes `validate_record()` but one or more records fail validation.

#### Scenario: One of three records invalid
- **WHEN** the envelope contains 3 records, 2 pass validation, 1 raises `SchemaValidationError`
- **THEN** `health_check(envelope)` returns `HealthReport(status=HealthStatus.DEGRADED, reason=...)` with a reason that names the failing field(s)

### Requirement: Classify envelope as broken when all records fail validation
The system SHALL return `HealthStatus.BROKEN` when every record in a non-empty `records` list fails `validate_record()`.

#### Scenario: All records invalid
- **WHEN** the envelope contains 2 records and both raise `SchemaValidationError`
- **THEN** `health_check(envelope)` returns `HealthReport(status=HealthStatus.BROKEN, reason=...)`

### Requirement: HealthReport is immutable
`HealthReport` SHALL be implemented as a frozen dataclass so callers cannot mutate the returned result.

#### Scenario: Attempt to mutate HealthReport
- **WHEN** a caller attempts to assign a new value to `health_report.status`
- **THEN** a `FrozenInstanceError` (or equivalent) is raised
