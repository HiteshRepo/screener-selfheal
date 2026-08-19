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


# Exact JavaScript parser code for each demo mirror layout.
# Used as a deterministic fallback when the OpenAI-generated prompt fails to
# produce a working refactor. Keyed by the layout marker found in the HTML.
_DEMO_PARSER_JS: dict[str, str] = {
    "layout: v1": """\
return {
  stocks: $('table.data-table tbody tr').toArray().map(row => {
    let $row = $(row);
    return {
      company_name: $row.find('td:nth-child(2) a').text_sane(),
      ticker: null,
      exchange: null,
      cmp: +$row.find('td:nth-child(3)').text_sane().replace(/,/g, '') || null,
      pe_ratio: +$row.find('td:nth-child(4)').text_sane() || null,
      market_cap_cr: $row.find('td:nth-child(5)').text_sane(),
      dividend_yield_pct: +$row.find('td:nth-child(6)').text_sane() || null,
      roce_pct: +$row.find('td:nth-child(7)').text_sane() || null,
      roe_pct: +$row.find('td:nth-child(8)').text_sane() || null,
      sales_growth_pct: $row.find('td:nth-child(9)').text_sane(),
      scraped_at: new Date().toISOString(),
      source_url: input.url
    };
  })
};""",
    "layout: v2": """\
return {
  stocks: $('.mirror-rows tr').toArray().map(row => {
    let $row = $(row);
    return {
      company_name: $row.find('td:nth-child(2) a').text_sane(),
      ticker: null,
      exchange: null,
      cmp: +$row.find('td:nth-child(3)').text_sane().replace(/,/g, '') || null,
      pe_ratio: +$row.find('td:nth-child(4)').text_sane() || null,
      market_cap_cr: $row.find('td:nth-child(5)').text_sane(),
      roce_pct: +$row.find('td:nth-child(6)').text_sane() || null,
      roe_pct: +$row.find('td:nth-child(7)').text_sane() || null,
      dividend_yield_pct: +$row.find('td:nth-child(8)').text_sane() || null,
      sales_growth_pct: $row.find('td:nth-child(9)').text_sane(),
      scraped_at: new Date().toISOString(),
      source_url: input.url
    };
  })
};""",
}


def generate_fallback_prompt(target_url: str) -> str | None:
    """Return a deterministic refactor prompt for demo mirror pages, or None.

    Fetches *target_url*, looks for a ``<!-- layout: v1 -->`` or
    ``<!-- layout: v2 -->`` marker, and returns a prompt containing the exact
    JavaScript parser code for that layout.  This is used as a fallback when
    the OpenAI-generated natural-language prompt fails to produce a working
    refactor on the first self-heal attempt.

    Returns None for non-demo pages so the caller can skip the fallback cycle.
    """
    try:
        html = _fetch_html(target_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallback: could not fetch HTML from %s: %s", target_url, exc)
        return None

    for marker, parser_js in _DEMO_PARSER_JS.items():
        if marker in html:
            logger.info("Fallback: demo mirror marker '%s' detected in %s.", marker, target_url)
            return (
                "The scraper selectors are broken for the current page layout. "
                "Replace the entire parser code with exactly this JavaScript — "
                "do not modify it:\n\n"
                f"{parser_js}"
            )

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
