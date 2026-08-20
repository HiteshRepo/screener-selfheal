# Alternating Mirror Layouts

## Purpose

The alternating mirror layouts provide two structurally distinct HTML files that render the same dividend yield stock data with different DOM structures. This enables the self-heal demo to break and recover CSS/XPath selectors by switching between layouts.

## Requirements

### Requirement: Two structurally distinct mirror layouts exist
The system SHALL provide two complete HTML files, `demo/mirror/v1.html` and `demo/mirror/v2.html`, each rendering the same dividend yield stock data but with structural DOM differences sufficient to break CSS/XPath selectors built for the other layout.

#### Scenario: v1 and v2 differ in table CSS class
- **WHEN** a CSS selector targeting `table.data-table` is applied to `v2.html`
- **THEN** the selector returns no elements (class is `screener-mirror` in v2)

#### Scenario: v1 and v2 differ in DOM nesting depth
- **WHEN** an XPath targeting `//div[@id="result"]/table` is applied to `v2.html`
- **THEN** the selector returns no elements (table is nested inside `.table-outer-wrapper > .table-inner-container` in v2)

#### Scenario: v1 and v2 differ in column header text
- **WHEN** a selector anchored to header text `"Dividend Yield"` is applied to `v2.html`
- **THEN** the selector returns no elements (header text is `"Div. Yield (%)"` in v2)

#### Scenario: Both layouts contain valid dividend data
- **WHEN** either layout is scraped by a correctly-configured collector
- **THEN** all records match the canonical schema in `data/schema.json`

### Requirement: Layout version is machine-readable
Each layout file SHALL include a comment `<!-- layout: v1 -->` or `<!-- layout: v2 -->` as the first line inside `<body>` so the active version can be detected by a shell `grep` without parsing HTML.

#### Scenario: Version marker present in v1
- **WHEN** `grep "layout: v1" demo/mirror/v1.html` is run
- **THEN** it exits 0 and prints the matching line

#### Scenario: Version marker present in v2
- **WHEN** `grep "layout: v2" demo/mirror/v2.html` is run
- **THEN** it exits 0 and prints the matching line

### Requirement: index.html is seeded from v1
`demo/mirror/index.html` SHALL be a copy of `v1.html` at initial commit so the demo collector starts in a known working state against the live layout.

#### Scenario: Initial index.html matches v1
- **WHEN** `diff demo/mirror/index.html demo/mirror/v1.html` is run on the initial commit
- **THEN** it exits 0 (files are identical)
