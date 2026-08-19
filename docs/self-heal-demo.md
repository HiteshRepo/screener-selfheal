# Self-Healing Demo

The demo shows Scraper Studio recovering when the target page layout changes unexpectedly.

For technical details on how the mirror page breaks the original selectors, see [`demo/README.md`](../demo/README.md).

## Setup

Enable GitHub Pages: **Settings → Pages → Source: `main` branch, `/ (root)`**

The mirror will be live at:

```
https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html
```

## Prerequisites

The following repo secrets must be configured:

| Secret | Purpose |
|--------|---------|
| `BRIGHT_DATA_API_TOKEN` | Bright Data API authentication |
| `BRIGHT_DATA_DEMO_COLLECTOR_ID` | Collector ID for the demo mirror page (separate from production) |
| `OPENAI_API_KEY` | OpenAI API key used by the self-heal script |

> **Note:** `BRIGHT_DATA_DEMO_COLLECTOR_ID` is distinct from the production `BRIGHT_DATA_COLLECTOR_ID`. Add it under **Settings → Secrets and variables → Actions → New repository secret** before running the demo.

## How It Works

The demo uses two static HTML fixtures with intentionally different DOM structures:

- **`demo/mirror/v1.html`** — mirrors the original Screener.in layout (`table.data-table`, `#result` direct parent, header `"Dividend Yield"`). The demo collector's selectors work against this layout.
- **`demo/mirror/v2.html`** — structurally altered layout (`table.screener-mirror`, nested inside `.table-outer-wrapper > .table-inner-container`, header `"Div. Yield (%)"`). The demo collector's selectors break against this layout.

`demo/mirror/index.html` is the live GitHub Pages file. The `break-mirror.yml` workflow flips it between v1 and v2 on each run, creating a fresh selector mismatch every time — no manual Bright Data reset needed.

## Step-by-Step Demo Sequence

**Step 1 — Break the mirror**

Trigger the `break-mirror.yml` workflow to swap the live layout to the opposite version:

```bash
# Via GitHub UI: Actions → Break Mirror → Run workflow
# OR via CLI:
gh workflow run break-mirror.yml
```

The workflow detects the current layout, copies the alternate version to `index.html`, and commits with `[skip ci]`. GitHub Pages will serve the new layout within ~30 seconds.

**Step 2 — Run the self-heal loop**

Trigger `selfheal-loop.yml` with `pages_just_updated` set to `true` so the workflow waits 30 seconds for Pages propagation before scraping:

```bash
# Via GitHub UI: Actions → Self-Heal Loop → Run workflow
#   target_url: https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html
#   pages_just_updated: true
# OR via CLI:
gh workflow run selfheal-loop.yml \
  -f target_url=https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html \
  -f pages_just_updated=true
```

Because `target_url` contains `github.io`, the workflow automatically uses `BRIGHT_DATA_DEMO_COLLECTOR_ID` — no manual input needed.

**Step 3 — Observe self-healing**

Watch the workflow run. The self-heal script will:
1. Detect that the current collector selectors return no data against the new layout
2. Use the OpenAI API to generate updated selectors
3. Push a PR with `data/latest.json` containing correctly extracted records

**Step 4 — Repeat**

Run `break-mirror.yml` again to flip back to the other layout, then trigger `selfheal-loop.yml` again. The demo is fully repeatable with no manual resets.
