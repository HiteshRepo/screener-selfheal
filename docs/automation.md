# GitHub Actions Automation

## `scrape-on-merge.yml`

Triggers on every push to `main`.

1. Checks out the repo
2. Installs dependencies
3. Runs `python src/run_scrape.py`
4. Runs `python src/run_diff.py`
5. Commits `data/production/latest.json` + today's change report back to `main` with `[skip ci]`

The `[skip ci]` tag prevents the bot commit from re-triggering the workflow.

---

## `break-mirror.yml`

Manual-dispatch only.

Swaps `demo/mirror/index.html` between v1 and v2 layouts on every run:

1. Detects the current layout by checking for `layout: v1` in `index.html`
2. Copies the alternate version (`v1.html` or `v2.html`) to `index.html`
3. Commits via a short-lived PR branch with `[skip ci]` and auto-merges to `main`
4. GitHub Pages serves the new layout within ~30 seconds

No inputs required — layout direction is detected automatically.

---

## `selfheal-loop.yml`

Manual-dispatch. Accepts two optional inputs:

| Input | Default | Description |
|---|---|---|
| `target_url` | GitHub Pages mirror URL | URL to scrape; determines demo vs production mode |
| `pages_just_updated` | `false` | If `true`, waits 30s for GitHub Pages to propagate before scraping |

**Collector auto-selection:** If `target_url` contains `github.io`, the workflow uses `BRIGHT_DATA_DEMO_COLLECTOR_ID`. Otherwise it uses `BRIGHT_DATA_COLLECTOR_ID`. No manual selection needed.

**Data directories:** Demo results go to `data/demo/latest.json`; production results go to `data/production/latest.json`.

**Workflow steps:**

1. Checkout repo and install dependencies
2. Optionally wait 30s for GitHub Pages propagation
3. Select the correct collector ID based on `target_url`
4. Run `python src/run_selfheal.py` (with optional `--target-url` override)
5. Commit results via a short-lived PR branch that auto-merges to `main`

See [self-heal-demo.md](./self-heal-demo.md) for the full demo walkthrough.
