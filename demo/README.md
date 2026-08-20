# Self-Healing Demo

This directory contains the static mirror pages used to demonstrate the self-healing loop.

## Mirror Page Structure

There are three HTML files:

| File | Role |
|---|---|
| `v1.html` | Layout fixture A — `table.data-table`, plain `<tbody>`, Dividend Yield at column 6 |
| `v2.html` | Layout fixture B — `table.screener-table`, `<tbody class="mirror-rows">`, ROCE at column 6 |
| `index.html` | The **live** file served by GitHub Pages — always a copy of either v1 or v2 |

Both layouts look visually identical to a human visitor. The differences are structural, in the HTML only:

| | v1 | v2 |
|---|---|---|
| Table class | `table.data-table` | `table.screener-table` |
| Container | `<div id="result">` | `<section id="screen-output"><div class="screener-wrapper">` |
| `<thead>` | bare | `<thead class="table-header">` |
| `<tbody>` | bare | `<tbody class="mirror-rows">` |
| Col 6 | Dividend Yield | ROCE % |
| Col 7 | ROCE % | ROE % |
| Col 8 | ROE % | Div. Yield (%) |

## How the Demo Works

`index.html` starts as a copy of v1. The `break-mirror.yml` workflow swaps it to the other layout on every run, creating a fresh selector mismatch — no manual Bright Data reset needed. The demo is fully repeatable.

### Why the Collector Breaks

The Bright Data demo collector is configured with selectors for one layout (e.g. `table.data-table tbody tr`). When `index.html` switches to v2, that selector finds nothing — the table class is now `screener-table` and the column order changed. The scrape returns `record_count: 0`.

### How the Self-Heal Fixes It

The self-heal loop (`run_selfheal.py`):
1. Detects the broken scrape (0 records returned)
2. Fetches the live `index.html` and parses it with BeautifulSoup to dynamically discover the table class, tbody class, and column headers
3. Builds a targeted prompt describing exactly which selector to change and the correct column order
4. Sends the prompt to Bright Data's `refactor_template` API
5. Validates the generated code using Bright Data's `preview_result` before approving — refuses to save if the preview returns 0 records
6. Approves and saves the new parser version

## Hosting

The mirror is hosted via **GitHub Pages** on the `main` branch at:

```
https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html
```

For local inspection, serve with Python's built-in server:

```bash
python3 -m http.server 8080 --directory .
# open http://localhost:8080/demo/mirror/index.html
```
