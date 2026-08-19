# Self-Healing Demo

The demo shows Scraper Studio recovering when the target page layout changes unexpectedly.

For technical details on how the mirror page breaks the original selectors, see [`demo/README.md`](../demo/README.md).

## Setup

Enable GitHub Pages: **Settings → Pages → Source: `main` branch, `/ (root)`**

The mirror will be live at:

```
https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html
```

## Step-by-Step

**Step 1 — Observe the failure**

The mirror page (`demo/mirror/index.html`) has deliberate layout alterations:
- Column header `"Dividend Yield"` renamed to `"Div. Yield (%)"`
- Table wrapped in an extra `<div class="data-wrapper">` layer
- CSS class `screener-table` renamed to `alt-table`

When the original collector selectors are applied to the mirror, the extraction is empty or malformed.

**Step 2 — Run the demo workflow**

```bash
# Trigger via GitHub UI: Actions → Self-Healing Demo → Run workflow
# OR via CLI:
gh workflow run selfheal-demo.yml
```

Observe `data/demo-latest.json` — it will be empty or contain malformed records, demonstrating the layout mismatch.

**Step 3 — Trigger Scraper Studio self-healing**

In the Bright Data Scraper Studio UI:
1. Open the collector
2. Point it at the mirror URL
3. Use the re-prompt / self-healing flow to regenerate selectors
4. Run again

Observe `data/demo-latest.json` — the collector now correctly extracts the sample rows.

**Step 4 — Compare before/after**

The before state is captured at `data/demo-before.json` (written at the start of the demo workflow before recovery). Use `python src/run_diff.py` with the demo paths to produce a change report.
