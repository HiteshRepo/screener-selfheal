# GitHub Actions Automation

## `scrape-on-merge.yml`

Triggers on every push to `main`.

1. Checks out the repo
2. Installs dependencies
3. Runs `python src/run_scrape.py`
4. Runs `python src/run_diff.py`
5. Commits `data/latest.json` + today's change report back to `main` with message `[skip ci] scrape results <timestamp>`

The `[skip ci]` tag prevents the bot commit from re-triggering the workflow (GitHub natively skips workflows for commits containing `[skip ci]` when using the default `GITHUB_TOKEN`).

## `selfheal-demo.yml`

Manual-dispatch only (`workflow_dispatch`).

Points the collector at the GitHub Pages mirror URL:

```
https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html
```

Writes results to `data/demo-latest.json`. Used to demonstrate the self-healing scenario — see [self-heal-demo.md](./self-heal-demo.md) for the full walkthrough.
