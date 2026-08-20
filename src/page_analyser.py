"""Page analyser: fetch target URL HTML via Bright Data Crawl API and call OpenAI to describe CSS/structural changes."""

import json
import logging
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup
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


_DEMO_LAYOUT_MARKERS = {"layout: v1", "layout: v2"}


def generate_fallback_prompt(target_url: str) -> str | None:
    """Dynamically analyse page HTML and return a targeted selector-fix prompt.

    Fetches *target_url*, checks for a demo mirror layout marker
    (``<!-- layout: v1 -->``, ``<!-- layout: v2 -->``), then parses the actual
    HTML structure with BeautifulSoup to discover the table class, tbody class,
    and column headers.  The resulting prompt tells Bright Data's refactor AI
    exactly which row selector to use and what the column order is — derived
    from what is actually in the HTML, not from any hardcoded lookup.

    Returns None for non-demo pages so the caller uses analyse_page() instead.
    """
    try:
        html = _fetch_html(target_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallback: could not fetch HTML from %s: %s", target_url, exc)
        return None

    if not any(marker in html for marker in _DEMO_LAYOUT_MARKERS):
        return None

    structure = _extract_table_structure(html)
    if not structure:
        logger.warning("Fallback: could not extract table structure from %s.", target_url)
        return None

    prompt = _build_selector_fix_prompt(structure)
    logger.info(
        "Fallback: generated targeted prompt from HTML structure — "
        "row_selector=%r columns=%r",
        structure["row_selector"],
        structure["columns"],
    )
    return prompt


def _extract_table_structure(html: str) -> dict | None:
    """Parse *html* and return scraping-relevant table structure, or None.

    Returns a dict with:
        row_selector  – jQuery selector string for data rows
        columns       – ordered list of column header texts
    """
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        return None

    table_classes = table.get("class") or []
    table_class = table_classes[0] if table_classes else ""

    tbody = table.find("tbody")
    tbody_classes = (tbody.get("class") or []) if tbody else []
    tbody_class = tbody_classes[0] if tbody_classes else ""

    if tbody_class:
        row_selector = f".{tbody_class} tr"
    elif table_class:
        row_selector = f"table.{table_class} tbody tr"
    else:
        row_selector = "table tbody tr"

    thead = table.find("thead")
    columns = [th.get_text(strip=True) for th in thead.find_all("th")] if thead else []

    return {"row_selector": row_selector, "columns": columns}


def _build_selector_fix_prompt(structure: dict) -> str:
    """Build a targeted Bright Data refactor prompt from extracted table structure."""
    columns_str = ", ".join(
        f"{i + 1}={col}" for i, col in enumerate(structure["columns"])
    )
    return (
        f"The current row selector is broken on this page. "
        f"Change the row selector to $('{structure['row_selector']}'). "
        f"Column order: {columns_str}."
    )


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
