"""Tests for src/page_analyser.py — analyse_page() with mocked Bright Data Crawl API and OpenAI."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SRC = os.path.join(_ROOT, "src")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from page_analyser import PageFetchError, _fetch_html, analyse_page  # noqa: E402
from src.scraper_client import ConfigurationError  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TARGET_URL = "https://www.screener.in/screens/dividend-yield/"
_SAMPLE_HTML = "<html><body>test</body></html>"

# Required schema field names (matches data/schema.json)
_SCHEMA_FIELDS = [
    "company_name",
    "ticker",
    "exchange",
    "cmp",
    "dividend_yield_pct",
    "scraped_at",
    "source_url",
]


def _crawl_response(html: str = _SAMPLE_HTML, status_code: int = 200) -> MagicMock:
    """Build a mock for the Bright Data Crawl API response."""
    resp = MagicMock()
    resp.ok = 200 <= status_code < 300
    resp.status_code = status_code
    resp.text = html
    resp.json.return_value = [{"html": html, "url": _TARGET_URL}]
    resp.raise_for_status = MagicMock(
        side_effect=None if resp.ok else Exception(f"HTTP {status_code}")
    )
    return resp


def _make_openai_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


# ---------------------------------------------------------------------------
# Tests: _fetch_html — Bright Data Crawl API
# ---------------------------------------------------------------------------


class TestFetchHtml:
    def test_raises_when_bright_data_token_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("BRIGHT_DATA_API_TOKEN", raising=False)
        with pytest.raises(ConfigurationError, match="BRIGHT_DATA_API_TOKEN"):
            _fetch_html(_TARGET_URL)

    def test_posts_to_crawl_api_with_correct_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BRIGHT_DATA_API_TOKEN", "test-bd-token")
        with patch("page_analyser.requests.post", return_value=_crawl_response()) as mock_post:
            _fetch_html(_TARGET_URL)
        call_kwargs = mock_post.call_args
        assert "datasets/v3/scrape" in call_kwargs.args[0]

    def test_sends_target_url_in_request_body(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BRIGHT_DATA_API_TOKEN", "test-bd-token")
        with patch("page_analyser.requests.post", return_value=_crawl_response()) as mock_post:
            _fetch_html(_TARGET_URL)
        body = mock_post.call_args.kwargs.get("json", {})
        assert any(inp.get("url") == _TARGET_URL for inp in body.get("input", []))

    def test_returns_html_from_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BRIGHT_DATA_API_TOKEN", "test-bd-token")
        with patch("page_analyser.requests.post", return_value=_crawl_response("<html>ok</html>")):
            html = _fetch_html(_TARGET_URL)
        assert html == "<html>ok</html>"

    def test_raises_page_fetch_error_on_non_2xx(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BRIGHT_DATA_API_TOKEN", "test-bd-token")
        bad_resp = _crawl_response(status_code=403)
        with patch("page_analyser.requests.post", return_value=bad_resp):
            with pytest.raises(PageFetchError, match="403"):
                _fetch_html(_TARGET_URL)

    def test_raises_page_fetch_error_when_html_key_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BRIGHT_DATA_API_TOKEN", "test-bd-token")
        resp = MagicMock()
        resp.ok = True
        resp.raise_for_status = MagicMock()
        resp.json.return_value = [{"url": _TARGET_URL}]  # no html/content/body/markdown
        with patch("page_analyser.requests.post", return_value=resp):
            with pytest.raises(PageFetchError, match="Could not extract HTML"):
                _fetch_html(_TARGET_URL)

    def test_raises_page_fetch_error_when_results_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BRIGHT_DATA_API_TOKEN", "test-bd-token")
        resp = MagicMock()
        resp.ok = True
        resp.raise_for_status = MagicMock()
        resp.json.return_value = []
        resp.text = "[]"
        with patch("page_analyser.requests.post", return_value=resp):
            with pytest.raises(PageFetchError, match="unexpected response"):
                _fetch_html(_TARGET_URL)


# ---------------------------------------------------------------------------
# Tests: analyse_page — missing API keys
# ---------------------------------------------------------------------------


class TestAnalysePageMissingApiKey:
    def test_missing_openai_key_raises_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
            analyse_page(_TARGET_URL)

    def test_missing_bright_data_token_raises_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("BRIGHT_DATA_API_TOKEN", raising=False)
        with pytest.raises(ConfigurationError, match="BRIGHT_DATA_API_TOKEN"):
            analyse_page(_TARGET_URL)


# ---------------------------------------------------------------------------
# Tests: analyse_page — HTML fetch and OpenAI call
# ---------------------------------------------------------------------------


class TestAnalysePageBehaviour:
    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        html: str = _SAMPLE_HTML,
        openai_content: str = "fix description",
    ) -> str:
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        monkeypatch.setenv("BRIGHT_DATA_API_TOKEN", "test-bd-token")
        with (
            patch("page_analyser.requests.post", return_value=_crawl_response(html)),
            patch("page_analyser.OpenAI") as mock_openai_cls,
        ):
            mock_openai_cls.return_value.chat.completions.create.return_value = (
                _make_openai_completion(openai_content)
            )
            return analyse_page(_TARGET_URL)

    def test_returns_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert isinstance(self._run(monkeypatch), str)

    def test_result_capped_at_900_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run(monkeypatch, openai_content="z" * 1200)
        assert len(result) <= 900

    def test_short_response_returned_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        short = "x" * 500
        assert self._run(monkeypatch, openai_content=short) == short

    def test_long_response_truncated_to_900(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert len(self._run(monkeypatch, openai_content="y" * 1200)) == 900


# ---------------------------------------------------------------------------
# Tests: OpenAI prompt content
# ---------------------------------------------------------------------------


class TestAnalysePagePromptContent:
    def _capture_prompt(self, monkeypatch: pytest.MonkeyPatch, html: str) -> str:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("BRIGHT_DATA_API_TOKEN", "test-bd-token")
        captured: list[str] = []

        def fake_create(**kwargs):
            for msg in kwargs.get("messages", []):
                captured.append(msg["content"])
            return _make_openai_completion("result")

        with (
            patch("page_analyser.requests.post", return_value=_crawl_response(html)),
            patch("page_analyser.OpenAI") as mock_openai_cls,
        ):
            mock_openai_cls.return_value.chat.completions.create.side_effect = fake_create
            analyse_page(_TARGET_URL)

        return " ".join(captured)

    def test_prompt_contains_all_schema_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prompt = self._capture_prompt(monkeypatch, html="<html>page</html>")
        for field in _SCHEMA_FIELDS:
            assert field in prompt, f"Expected schema field '{field}' in prompt"

    def test_prompt_contains_fetched_html(self, monkeypatch: pytest.MonkeyPatch) -> None:
        unique_marker = "unique-marker-abc123"
        html = f"<html><div class='{unique_marker}'>data</div></html>"
        prompt = self._capture_prompt(monkeypatch, html=html)
        assert unique_marker in prompt
