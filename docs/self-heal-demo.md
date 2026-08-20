# Self-Healing Demo

The demo shows Scraper Studio recovering when the target page layout changes unexpectedly.

For technical details on the mirror page structure, see [`demo/README.md`](../demo/README.md).

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
| `OPENAI_API_KEY` | OpenAI API key used by the page analyser fallback |

> **Note:** `BRIGHT_DATA_DEMO_COLLECTOR_ID` is distinct from the production `BRIGHT_DATA_COLLECTOR_ID`. Add it under **Settings → Secrets and variables → Actions → New repository secret** before running the demo.

## How It Works

The demo uses two static HTML fixtures with identical visual appearance but different DOM structures:

- **`demo/mirror/v1.html`** — `table.data-table` inside `div#result`, plain `<tbody>`, column order: Dividend Yield → ROCE → ROE
- **`demo/mirror/v2.html`** — `table.screener-table` inside `section#screen-output`, `<tbody class="mirror-rows">`, column order: ROCE → ROE → Div. Yield (%)

`demo/mirror/index.html` is the live GitHub Pages file. The `break-mirror.yml` workflow flips it between v1 and v2 on each run, creating a fresh selector mismatch every time — no manual Bright Data reset needed.

## Step-by-Step Demo Sequence

**Step 1 — Break the mirror**

Trigger the `break-mirror.yml` workflow to swap the live layout:

```bash
# Via GitHub UI: Actions → Break Mirror → Run workflow
# OR via CLI:
gh workflow run break-mirror.yml
```

The workflow detects the current layout, copies the alternate version to `index.html`, and commits with `[skip ci]`. GitHub Pages will serve the new layout within ~30 seconds.

**Step 2 — Run the self-heal loop**

Trigger `selfheal-loop.yml` with `pages_just_updated` set to `true`:

```bash
# Via GitHub UI: Actions → Self-Heal Loop → Run workflow
#   target_url: https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html
#   pages_just_updated: true
# OR via CLI:
gh workflow run selfheal-loop.yml \
  -f target_url=https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html \
  -f pages_just_updated=true
```

Because `target_url` contains `github.io`, the workflow automatically uses `BRIGHT_DATA_DEMO_COLLECTOR_ID` — no manual selection needed. Results are written to `data/demo/latest.json`.

**Step 3 — Observe self-healing**

Watch the workflow run. The self-heal script will:

1. Detect that the collector returns 0 records against the new layout (BROKEN)
2. Fetch the live page HTML and parse it with BeautifulSoup to discover the table class, tbody class, and column headers — no hardcoded selector knowledge
3. Build a targeted natural-language prompt (e.g. "change the row selector to `$('.mirror-rows tr')`")
4. Send the prompt to Bright Data's `refactor_template` API
5. Poll until Bright Data's AI generates updated parser code and tests it against the live page
6. Inspect `preview_result` — only approve if the generated code returned records; refuse to save broken code
7. Save the new parser version to Bright Data

The run summary will show `recovery_status=refactor_approved_demo`. Run `selfheal-loop.yml` once more (without breaking) to confirm `recovery_status=not_needed` and see `data/demo/latest.json` committed with 5 records.

**Step 4 — Repeat**

Run `break-mirror.yml` again to flip to the other layout, then trigger `selfheal-loop.yml` again. The demo is fully repeatable with no manual resets.
