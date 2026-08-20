# Claude CLI Prompt — Into the Scrape-Verse Hackathon

Paste this as your opening prompt to Claude Code (`claude` CLI) in an empty project directory. Fill in the `[bracketed]` spots before running it.

---

## PROMPT

I'm building a hackathon project for "Into the Scrape-Verse" (WeMakeDevs, Bright Data track). Read this whole brief before writing any code, then propose a short plan before you start.

### What we're building
A self-healing web scraper + a real downstream product on top of it, so that when the target website changes its layout, the scraper repairs itself instead of silently breaking or returning empty/garbage data.

**This project's repo:** `https://github.com/HiteshRepo/screener-selfheal` (new, created for this hackathon).

**Existing dividend tracker repo (for reference/extension):** `https://github.com/HiteshRepo/stock-screeners`, cloned locally at `../stock-screeners/` relative to this project — read its current structure (how it stores/reads dividend data, its markdown file format and layout) before building the integration, so the new data layer stays consistent with it rather than inventing a new format. Decide with me whether the integration lives directly in `stock-screeners`, or in `screener-selfheal` reading/writing to a shared format — flag this as an early architecture decision rather than assuming.

**Domain:** Indian stock market / personal investing data.

**Target site for the scraper (public data only, no login):**
- Primary and only target for this week: Screener.in's **"Highest Dividend Yield Shares"** screen — `https://www.screener.in/screens/3/highest-dividend-yield-shares/` — stocks that have been consistently paying dividends, sorted by highest yield. Returns a table of multiple companies with their metric columns in one scrape. No login required.
- NSE/BSE public corporate announcements: explicitly OUT of scope for this build. Don't build a second collector or scraper for it. Mention it as a natural "future work" extension in the README only — nothing more.

**Downstream product:** Extend my existing personal dividend portfolio tracker. Today it's a Python CLI that reads/writes local markdown files, advisory-only (no broker API), used to build an accuracy/track-record over time. This hackathon adds an **automated data refresh layer**: the scraper pulls the current screen table (all tracked dividend stocks) on a schedule, diffs it against what's stored, and flags meaningful changes per company (new dividend declared, ratio moved past a threshold, entered/left the screen) — instead of me manually checking Screener.in one stock at a time.

**Automation:** This lives in a public GitHub repo with a GitHub Actions workflow that triggers the Scraper Studio collector (via the `/dca/trigger` + `/dca/dataset` API) automatically on merge to `main`, writes the results into the repo (e.g. `data/latest.json`), and commits them back — so the repo's git history doubles as a visible log of scrape runs over time. A separate, clearly-labeled workflow (or manual trigger) points the scraper at a deliberately modified/mirrored version of the target page, for the self-healing demo.

**Collector already created** — I built this in Scraper Studio's AI Agent mode myself (not something you need to create):
- Collector ID: `c_msvhzc3s2gixuk6k42`
- Fields the collector extracts: company name, NSE/BSE ticker symbol, current market price (CMP), dividend yield %, P/E ratio, market cap, and any other ratio columns present on the screen (e.g. ROCE, ROE, sales growth); pagination handled so all rows across pages are captured.
- API token: I'll add this as a repo secret (`BRIGHT_DATA_API_TOKEN`) — don't ask me to paste it in chat.

### Hard requirements (hackathon rules — do not violate)
1. The scraper MUST be built with **Bright Data Scraper Studio** — not just a pre-built scraper from Bright Data's existing library. It has to be a custom collector I create for this target site.
2. Public data only. No login-gated, paywalled, or personal data.
3. Must demonstrate **self-healing**: when the site's DOM/layout changes, the scraper should detect the mismatch and recover (via Scraper Studio's self-healing mechanism), not just fail silently.
4. Final submission needs: public repo, clear README, example structured output (JSON/CSV sample), demo video, and a clear written explanation of how Scraper Studio is used.
5. I need to be able to explain every part of this — don't generate anything I can't walk through myself. Explain your architectural decisions as you go, in plain terms.
6. Any AI-assisted code must be disclosed in the README (it will be — you're helping me build this).

### What I need from you in this session
1. **Propose the architecture first** — components, data flow, where Scraper Studio fits vs. where custom code fits, before writing files. Keep it as simple as possible; this is a one-week build, not a production system.
2. **Scraper Studio API integration**: the collector already exists (ID above) — write the trigger/poll/download script that calls `/dca/trigger` (with the collector ID) and polls `/dca/dataset` until results are ready, using the official Node.js or Python boilerplate as a starting point rather than reinventing it. Don't recreate the collector.
3. **Self-healing demo plan**: since the live site probably won't break mid-week, help me design a deliberate demo — e.g., a mirrored/modified copy of the target page with an altered layout, so I can show the scraper failing on the old selector logic and recovering via Scraper Studio's self-healing/re-prompt flow, with a clear before/after in the demo video.
4. **Downstream product code**: extend the dividend tracker's data layer to consume the scraper's structured output, diff it against stored state, and surface changes (new file, log entry, or simple CLI output — keep this consistent with the tracker's existing markdown-file-based, advisory-only style).
5. **Output schema**: define a clean structured output (JSON) matching the collector's actual fields (name, ticker, CMP, dividend yield, P/E, market cap, other ratio columns) — one record per company per scrape, plus scraped_at timestamp and source_url — usable both as the "example structured output" deliverable and as tracker input.
6. **GitHub Actions workflow**: set up `.github/workflows/scrape-on-merge.yml` to run the trigger/poll/download script on push to `main`, using repo secrets for the Bright Data API token and collector ID, and commit the results back to `data/latest.json` (skip-ci on the bot's own commit to avoid loops). Add a second workflow or manual-dispatch job for the self-healing demo run against the modified/mirrored page.
7. **README**: draft one that covers setup, how Scraper Studio is used, the GitHub Actions automation, the self-healing demo, architecture diagram (text/mermaid is fine), and AI-assistance disclosure.
8. Flag anything in this plan that risks violating the hackathon rules (e.g., accidentally scraping something login-gated) before we build it.

Start by restating the architecture plan in 5-8 bullets and confirming the primary scrape target with me before writing code.

---

## Before you run this
- [x] Collector ID confirmed: `c_msvhzc3s2gixuk6k42`
- [x] Stretch target (NSE/BSE announcements) decided: out of scope for this week, README future-work mention only
- [x] Team size confirmed: solo
- [x] `stock-screeners` cloned locally at `../stock-screeners/` relative to `screener-selfheal`
- [x] Repo secrets added: `BRIGHT_DATA_API_TOKEN` and `BRIGHT_DATA_COLLECTOR_ID` (Settings → Secrets and variables → Actions)
