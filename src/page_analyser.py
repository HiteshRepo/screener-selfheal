"""Page analyser: fetch target URL HTML via Bright Data Crawl API and call OpenAI to describe CSS/structural changes."""

import json
import logging
import os
from pathlib import Path

import requests
from openai import OpenAI

from src.scraper_client import ConfigurationError

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent / "data" / "schema.json"
_MAX_HTML_CHARS = 30_000  # safe token-budget approximation (~7 500 tokens)
_MAX_FIX_CHARS = 900

_BRIGHT_DATA_BASE_URL = "https://api.brightdata.com"
_BRIGHT_DATA_CRAWL_DATASET_ID = "gd_m6gjtfmeh43we6cqc"
_CRAWL_TIMEOUT = 60  # seconds


class PageFetchError(Exception):
    """Raised when the target URL cannot be fetched."""


# Targeted selector-fix prompts for each demo mirror layout.
# These describe *what to change* in plain language rather than providing
# verbatim code. Bright Data's refactor AI acts on targeted instructions
# reliably; it ignores "use exactly this code" prompts and rewrites freely.
# Keyed by the layout marker found in the HTML body.
_DEMO_FIX_PROMPTS: dict[str, str] = {
    "layout: v1": (
        "The current row selector is broken on this page. "
        "The table uses class 'data-table' inside a div with id 'result'. "
        "The tbody has no class. "
        "Change the row selector to $('table.data-table tbody tr'). "
        "Column order: 1=S.No, 2=Name(a tag), 3=CMP, 4=P/E, 5=MktCap, "
        "6=DividendYield(dividend_yield_pct), 7=ROCE(roce_pct), 8=ROE(roe_pct), 9=SalesGrowth."
    ),
    "layout: v2": (
        "The current row selector is broken on this page. "
        "The table uses class 'screener-table' inside a section with id 'screen-output'. "
        "The tbody has class 'mirror-rows'. "
        "Change the row selector to $('.mirror-rows tr'). "
        "Column order: 1=S.No, 2=Name(a tag), 3=CMP, 4=P/E, 5=MktCap, "
        "6=ROCE(roce_pct), 7=ROE(roe_pct), 8=DividendYield(dividend_yield_pct), 9=SalesGrowth."
    ),
}


def generate_fallback_prompt(target_url: str) -> str | None:
    """Return a targeted selector-fix prompt for demo mirror pages, or None.

    Fetches *target_url*, looks for a ``<!-- layout: v1 -->`` or
    ``<!-- layout: v2 -->`` marker, and returns a targeted natural-language
    prompt describing exactly which selector to change and the correct column
    order.  Bright Data's refactor AI responds reliably to targeted selector
    instructions; verbatim code replacement prompts are ignored.

    Returns None for non-demo pages so the caller uses analyse_page() instead.
    """
    try:
        html = _fetch_html(target_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallback: could not fetch HTML from %s: %s", target_url, exc)
        return None

    for marker, prompt in _DEMO_FIX_PROMPTS.items():
        if marker in html:
            logger.info("Fallback: demo mirror marker '%s' detected in %s.", marker, target_url)
            return prompt

    return None


def _load_schema_fields() -> list[str]:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    return list(schema.get("properties", {}).keys())


def _fetch_html(target_url: str) -> str:
    """Fetch HTML from *target_url* via Bright Data Crawl API.

    Bright Data's infrastructure can reach sites (e.g. screener.in) that
    block GitHub Actions IP ranges, so we route the fetch through their
    Crawl API rather than using a direct requests.get().

    Raises:
        ConfigurationError: if BRIGHT_DATA_API_TOKEN is not set.
        PageFetchError: if the Crawl API call fails or returns no HTML.
    """
    token = os.environ.get("BRIGHT_DATA_API_TOKEN")
    if not token:
        raise ConfigurationError("BRIGHT_DATA_API_TOKEN is not set in the environment.")

    response = requests.post(
        f"{_BRIGHT_DATA_BASE_URL}/datasets/v3/scrape",
        params={
            "dataset_id": _BRIGHT_DATA_CRAWL_DATASET_ID,
            "notify": "false",
            "include_errors": "true",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"input": [{"url": target_url}], "limit_per_input": None},
        timeout=_CRAWL_TIMEOUT,
    )

    if not response.ok:
        raise PageFetchError(
            f"Bright Data Crawl API returned HTTP {response.status_code}: {response.text[:200]}"
        )

    results = response.json()
    if isinstance(results, dict):
        item = results
    elif isinstance(results, list) and results:
        item = results[0]
    else:
        raise PageFetchError(
            f"Bright Data Crawl API returned unexpected response: {response.text[:200]}"
        )
    html = (
        item.get("page_html")
        or item.get("html")
        or item.get("content")
        or item.get("body")
        or item.get("markdown")
    )
    if not html:
        raise PageFetchError(
            f"Could not extract HTML from Crawl API response. Keys present: {list(item.keys())}"
        )

    return html


def analyse_page(target_url: str) -> str:
    """Fetch *target_url* via Bright Data, call OpenAI gpt-4o, and return a fix description (≤900 chars).

    Args:
        target_url: URL of the page to analyse.

    Returns:
        String describing what changed and how selectors should be updated (at most 900 chars).

    Raises:
        ConfigurationError: if OPENAI_API_KEY or BRIGHT_DATA_API_TOKEN is not set.
        PageFetchError: if the page cannot be fetched via the Crawl API.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ConfigurationError("OPENAI_API_KEY is not set in the environment.")

    html = _fetch_html(target_url)
    html = html[:_MAX_HTML_CHARS]

    schema_fields = _load_schema_fields()
    fields_str = ", ".join(schema_fields)

    prompt = (
        f"You are a web scraping expert. The following HTML was fetched from {target_url}.\n\n"
        f"The canonical schema requires these fields: {fields_str}.\n\n"
        f"Analyse the HTML and identify which CSS selectors or structural elements map to each "
        f"required field. Describe what may have changed in the page structure that would cause "
        f"a scraper to fail, and suggest how the CSS selectors should be updated.\n\n"
        f"HTML:\n{html}"
    )

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )

    description = completion.choices[0].message.content or ""
    return description[:_MAX_FIX_CHARS]
