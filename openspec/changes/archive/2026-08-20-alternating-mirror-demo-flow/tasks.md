## 1. Mirror Layout Files

- [x] 1.1 Create `demo/mirror/v1.html` — layout matching current collector selectors (`table.data-table`, direct child of `#result`, header `Dividend Yield`), with `<!-- layout: v1 -->` as first line inside `<body>`, using sample data from `data/sample.json`
- [x] 1.2 Create `demo/mirror/v2.html` — structurally different layout (`table.screener-mirror`, nested inside `.table-outer-wrapper > .table-inner-container`, header `Div. Yield (%)`, ROCE/ROE columns before yield), with `<!-- layout: v2 -->` as first line inside `<body>`, same sample data
- [x] 1.3 Replace `demo/mirror/index.html` with a copy of `v1.html` (seed the live page to a known working state)
- [x] 1.4 Verify `diff demo/mirror/index.html demo/mirror/v1.html` exits 0

## 2. break-mirror Workflow

- [x] 2.1 Create `.github/workflows/break-mirror.yml` with `workflow_dispatch` trigger and `permissions: contents: write`
- [x] 2.2 Add version-detection step: `grep -q "layout: v1" demo/mirror/index.html` to set `CURRENT_LAYOUT` env var
- [x] 2.3 Add file-swap step: copy `v2.html` → `index.html` if current is v1, else copy `v1.html` → `index.html`
- [x] 2.4 Add commit + push step with message `chore: switch mirror layout to v<N> [skip ci]`
- [x] 2.5 Add step summary output: `echo "Mirror is now layout v<N>" >> $GITHUB_STEP_SUMMARY`

## 3. selfheal-loop Workflow Updates

- [x] 3.1 Add `pages_just_updated` boolean input (default: `false`) to `workflow_dispatch` inputs in `selfheal-loop.yml`
- [x] 3.2 Add conditional sleep step: `if: inputs.pages_just_updated == 'true'` → `sleep 30`
- [x] 3.3 Add collector-selection logic: if `target_url` contains `github.io`, set `BRIGHT_DATA_COLLECTOR_ID` from `secrets.BRIGHT_DATA_DEMO_COLLECTOR_ID`; otherwise use `secrets.BRIGHT_DATA_COLLECTOR_ID`
- [x] 3.4 Update default value of `target_url` input to `https://hiteshrepo.github.io/screener-selfheal/demo/mirror/index.html`

## 4. Docs Update

- [x] 4.1 Update `docs/self-heal-demo.md` to document the alternating-layout demo sequence: `break-mirror.yml` → wait → `selfheal-loop.yml` with `pages_just_updated: true`
- [x] 4.2 Note in `docs/self-heal-demo.md` that `BRIGHT_DATA_DEMO_COLLECTOR_ID` must be added as a repo secret
