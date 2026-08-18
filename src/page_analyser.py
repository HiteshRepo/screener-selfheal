"""Page analyser: fetch target URL HTML and call OpenAI to describe CSS/structural changes."""

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


def _load_schema_fields() -> list[str]:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    return list(schema.get("properties", {}).keys())


def analyse_page(target_url: str) -> str:
    """Fetch *target_url*, call OpenAI gpt-4o, and return a fix description (≤900 chars).

    Args:
        target_url: URL of the page to analyse.

    Returns:
        String describing what changed and how selectors should be updated (at most 900 chars).

    Raises:
        ConfigurationError: if OPENAI_API_KEY is not set in the environment.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ConfigurationError("OPENAI_API_KEY is not set in the environment.")

    response = requests.get(target_url)
    if response.status_code != 200:
        logger.warning(
            "Non-200 response fetching %s: status=%d", target_url, response.status_code
        )

    html = response.text[:_MAX_HTML_CHARS]
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
