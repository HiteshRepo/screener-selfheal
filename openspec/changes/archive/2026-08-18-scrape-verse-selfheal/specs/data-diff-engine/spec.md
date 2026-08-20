## ADDED Requirements

### Requirement: Load and compare snapshots
The diff engine SHALL load `data/latest.json` and `data/previous.json`, match records by ticker symbol, and classify each company into one of four change categories.

**Change categories:**
- `ENTERED`: ticker present in latest but not in previous
- `EXITED`: ticker present in previous but not in latest
- `CHANGED`: ticker present in both; one or more tracked fields moved past threshold
- `UNCHANGED`: ticker present in both; no tracked fields exceeded threshold

#### Scenario: Company enters the screen
- **WHEN** a ticker appears in `data/latest.json` but not in `data/previous.json`
- **THEN** the diff engine classifies it as `ENTERED` and includes its full record in the report

#### Scenario: Company exits the screen
- **WHEN** a ticker appears in `data/previous.json` but not in `data/latest.json`
- **THEN** the diff engine classifies it as `EXITED` and records its last known values

#### Scenario: No previous snapshot
- **WHEN** `data/previous.json` does not exist
- **THEN** the diff engine treats all records as `ENTERED` and notes in the report that this is the first run

### Requirement: Field change thresholds
The diff engine SHALL flag a `CHANGED` classification only when at least one tracked field changes by more than a configurable threshold.

**Default thresholds:**
- `dividend_yield_pct`: 0.5 percentage points
- `cmp`: 5% relative change
- `pe_ratio`: 2.0 absolute change
- All other fields: any non-null change

#### Scenario: Yield change exceeds threshold
- **WHEN** `dividend_yield_pct` changes by more than 0.5 pp between snapshots
- **THEN** the company is classified as `CHANGED` and the delta is included in the report

#### Scenario: Yield change within threshold
- **WHEN** `dividend_yield_pct` changes by 0.3 pp (below default threshold)
- **THEN** the company is classified as `UNCHANGED` and omitted from the change report

#### Scenario: Custom threshold via config
- **WHEN** the caller provides a `thresholds` dict overriding defaults
- **THEN** the diff engine uses the caller-supplied values instead of defaults

### Requirement: Markdown change report output
The diff engine SHALL write a human-readable Markdown change report to a dated file `data/changes-YYYY-MM-DD.md` matching the advisory-only, file-based style of the existing `stock-screeners` tracker.

**Report structure:**
- Header: date and source snapshot paths
- Section per category: ENTERED, EXITED, CHANGED (UNCHANGED companies are omitted)
- Each entry: company name, ticker, changed fields with old → new values
- Footer: total counts per category

#### Scenario: Report written on changes detected
- **WHEN** at least one company is classified as ENTERED, EXITED, or CHANGED
- **THEN** a dated Markdown file is written to `data/`

#### Scenario: No-change run
- **WHEN** all companies are classified as UNCHANGED
- **THEN** the diff engine writes a brief no-change report and logs the result; no error is raised

#### Scenario: Report filename uses scrape date
- **WHEN** `data/latest.json` has `meta.scraped_at = "2024-06-15T10:00:00Z"`
- **THEN** the report is written to `data/changes-2024-06-15.md`
