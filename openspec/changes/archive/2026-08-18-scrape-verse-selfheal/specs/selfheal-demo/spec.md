## ADDED Requirements

### Requirement: Static mirror page with altered layout
A self-contained HTML file `demo/mirror/index.html` SHALL replicate the visual structure of the Screener.in "Highest Dividend Yield Shares" screen with deliberate layout alterations that break the original collector's selector logic.

**Required alterations (at least two of the following):**
- Column header names changed (e.g., `"Dividend Yield"` → `"Div. Yield (%)"`)
- Table wrapped in an additional `<div>` layer changing the DOM depth
- CSS class names on the table or rows renamed
- Column order shuffled

#### Scenario: Mirror page loads in a browser
- **WHEN** `demo/mirror/index.html` is opened in a browser or served via HTTP
- **THEN** a table of sample dividend yield data is visible with altered column headers or structure

#### Scenario: Original selector fails on mirror
- **WHEN** the collector's original selector logic is applied to the mirror page
- **THEN** the extracted data is empty or malformed, demonstrating the layout mismatch

### Requirement: Sample data in mirror page
The mirror page SHALL contain at least 5 sample company rows with realistic but fictional or public-domain data (not live scraped data from Screener.in).

#### Scenario: Mirror contains sample rows
- **WHEN** the mirror page is parsed
- **THEN** at least 5 `<tr>` rows containing company name, ticker, and numeric fields are present

#### Scenario: Sample data is clearly labeled as demo
- **WHEN** the mirror page is viewed
- **THEN** a visible banner or HTML comment identifies the page as a test fixture, not live data

### Requirement: Demo run evidence
The self-healing demo SHALL produce before/after evidence suitable for inclusion in the demo video: a failed extraction attempt and a successful recovery.

#### Scenario: Failed extraction logged
- **WHEN** the `selfheal-demo` workflow runs against the mirror URL with the original collector configuration
- **THEN** the scraper client logs or returns an empty/malformed result set, and this state is captured in `data/demo-before.json`

#### Scenario: Recovery documented in README
- **WHEN** a reader follows the demo section of the README
- **THEN** they can reproduce the failure, trigger Scraper Studio's self-healing / re-prompt flow, and observe the successful extraction, all within the `selfheal-demo` workflow

### Requirement: Mirror hosting strategy
The mirror page SHALL be serveable without a dedicated web server for CI environments.

#### Scenario: Raw GitHub URL serves the mirror
- **WHEN** the `selfheal-demo` workflow sets `DEMO_TARGET_URL` to the raw GitHub content URL of `demo/mirror/index.html`
- **THEN** the scraper client can fetch the page content without additional infrastructure

#### Scenario: Fallback to local HTTP server in CI
- **WHEN** the raw GitHub URL approach is unavailable or returns incorrect content-type
- **THEN** the `selfheal-demo` workflow starts a `python3 -m http.server` in the background and uses `http://localhost:8080/demo/mirror/index.html` as the target URL
