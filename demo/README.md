# Self-Healing Demo

This directory contains the static mirror page used to demonstrate Bright Data
Scraper Studio's self-healing capability.

## What Is the Mirror Page?

`demo/mirror/index.html` is a **test fixture** — a static HTML page that
deliberately replicates the *visual* structure of the Screener.in
"Highest Dividend Yield Shares" screen while introducing four layout
alterations that break the original collector's selector logic:

| Alteration | Original (Screener.in) | Mirror (`index.html`) |
|---|---|---|
| Table CSS class | `class="data-table"` | `class="screener-mirror"` |
| Extra `<div>` wrapper | Table is a direct child of `<div id="result">` | Table is nested inside `.table-outer-wrapper > .table-inner-container` |
| Column header name | `Dividend Yield` | `Div. Yield (%)` |
| Column order | ROCE / ROE appear *after* Dividend Yield | ROCE / ROE appear *before* Div. Yield (%) |

## Why the Original Selector Fails

A typical Bright Data collector configured against `screener.in` uses CSS or
XPath selectors such as:

```
CSS:   table.data-table > tbody > tr
XPath: //table[@class='data-table']//tr
```

When this selector logic is applied to the mirror page:

1. **`table.data-table` does not exist** — the class was renamed to
   `screener-mirror`. The selector returns **no elements**, producing an
   **empty result set**.

2. **Even if the table were found**, the column index for `"Dividend Yield"`
   differs (column 8 in the mirror vs. column 6 on the live site, and the
   header text is different). Any field-extraction rule anchored to the header
   text `"Dividend Yield"` or to a hard-coded column index will return
   **`null` / empty strings** for every record.

3. **XPath depth mismatch** — the extra `.table-outer-wrapper >
   .table-inner-container` wrapper layers change the DOM depth, breaking
   absolute XPath expressions.

### Evidence of Failure

Running the scraper against the mirror URL without updating the collector
produces output similar to:

```json
{
  "meta": {
    "scraped_at": "2026-08-18T10:00:00Z",
    "source_url": "https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html",
    "collector_id": "<collector-id>",
    "record_count": 0
  },
  "records": []
}
```

This empty (or malformed) result is captured as `data/demo-before.json` during
the `selfheal-demo` workflow run.

## Self-Healing Flow (Step-by-Step)

1. **Trigger failure**: Run the `selfheal-demo` GitHub Actions workflow.
   The workflow sets `DEMO_TARGET_URL` to the GitHub Pages URL of this mirror
   page and calls `python src/run_scrape.py`. The result (`data/demo-before.json`)
   contains `record_count: 0`.

2. **Open Scraper Studio**: In the Bright Data dashboard, open the collector
   and navigate to the "Self-Healing" or "Re-prompt" panel.

3. **Re-prompt with updated selectors**: Provide the corrected selectors or let
   the Studio AI detect the new class names (`screener-mirror`, updated column
   headers). Apply the suggested fix.

4. **Re-run**: Trigger the `selfheal-demo` workflow again. The scraper now
   finds `table.screener-mirror` and maps `Div. Yield (%)` to
   `dividend_yield_pct`. The result (`data/demo-latest.json`) contains 6 records.

5. **Compare**: The diff engine can be run against `demo-before.json` and
   `demo-latest.json` to show the ENTERED tickers as evidence of recovery.

## Hosting the Mirror Page

The mirror page is hosted via **GitHub Pages** on the `main` branch at:

```
https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html
```

For local testing, serve it with Python's built-in HTTP server:

```bash
python3 -m http.server 8080 --directory .
# then open http://localhost:8080/demo/mirror/index.html
```
