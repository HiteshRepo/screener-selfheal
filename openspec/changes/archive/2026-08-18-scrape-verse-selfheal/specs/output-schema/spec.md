## ADDED Requirements

### Requirement: Canonical record structure
Each scraped company record SHALL conform to a defined JSON schema with required and optional fields. The schema is the single source of truth for all downstream consumers.

**Required fields:**
- `company_name` (string): Full company name as displayed on Screener.in
- `ticker` (string): NSE or BSE ticker symbol (e.g., `"INFY"`)
- `exchange` (string): `"NSE"` or `"BSE"`
- `cmp` (number): Current market price in INR
- `dividend_yield_pct` (number): Dividend yield as a percentage (e.g., `3.5` for 3.5%)
- `scraped_at` (string, ISO 8601): UTC timestamp of when the scrape completed
- `source_url` (string): Full URL of the screen that was scraped

**Optional fields (present when available on the page):**
- `pe_ratio` (number | null)
- `market_cap_cr` (number | null): Market cap in crores INR
- `roce_pct` (number | null)
- `roe_pct` (number | null)
- `sales_growth_pct` (number | null)

#### Scenario: Valid record passes schema validation
- **WHEN** a record contains all required fields with correct types
- **THEN** schema validation returns no errors

#### Scenario: Missing required field fails validation
- **WHEN** a record is missing `ticker` or `dividend_yield_pct`
- **THEN** schema validation raises a `SchemaValidationError` naming the missing field

#### Scenario: Null optional fields are accepted
- **WHEN** `pe_ratio` or any optional field is `null`
- **THEN** schema validation passes without error

### Requirement: Dataset envelope
The full downloaded dataset SHALL be a JSON array of canonical records, optionally wrapped in a metadata envelope at the top level.

**Envelope structure:**
```json
{
  "meta": {
    "scraped_at": "<ISO 8601 UTC>",
    "source_url": "<string>",
    "collector_id": "<string>",
    "record_count": "<integer>"
  },
  "records": [ /* array of canonical records */ ]
}
```

#### Scenario: Envelope written to data/latest.json
- **WHEN** a successful scrape completes
- **THEN** `data/latest.json` contains a valid envelope with `meta` and `records` keys

#### Scenario: Record count matches records array length
- **WHEN** `data/latest.json` is read
- **THEN** `meta.record_count` equals `len(records)`

### Requirement: Schema documentation file
A `data/schema.json` file SHALL be committed to the repo as the machine-readable JSON Schema (Draft 7) describing the canonical record structure.

#### Scenario: Schema file is valid JSON Schema
- **WHEN** `data/schema.json` is loaded by a JSON Schema validator
- **THEN** it validates without errors and describes all required and optional fields

#### Scenario: Sample records validate against schema
- **WHEN** sample records from `data/latest.json` are validated against `data/schema.json`
- **THEN** all records pass validation
