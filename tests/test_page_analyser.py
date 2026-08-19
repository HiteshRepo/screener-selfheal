"""Tests for src/page_analyser.py — analyse_page() with mocked HTTP and OpenAI."""

import logging
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

from page_analyser import PageFetchError, analyse_page  # noqa: E402
from src.scraper_client import ConfigurationError  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TARGET_URL = "https://www.screener.in/screens/dividend-yield/"

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


def _make_http_response(status_code: int = 200, text: str = "<html>test</html>") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def _make_openai_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


# ---------------------------------------------------------------------------
# Tests: missing API key
# ---------------------------------------------------------------------------


class TestAnalysePageMissingApiKey:
    def test_missing_api_key_raises_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ConfigurationError):
            analyse_page(_TARGET_URL)


# ---------------------------------------------------------------------------
# Tests: HTTP fetch behaviour
# ---------------------------------------------------------------------------


class TestAnalysePageHttpFetch:
    def test_requests_get_called_once_with_target_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        with (
            patch("page_analyser.requests.get", return_value=_make_http_response()) as mock_get,
            patch("page_analyser.OpenAI") as mock_openai_cls,
        ):
            mock_openai_cls.return_value.chat.completions.create.return_value = (
                _make_openai_completion("fix description")
            )
            analyse_page(_TARGET_URL)
        mock_get.assert_called_once_with(_TARGET_URL)

    def test_raises_page_fetch_error_on_404(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        with (
            patch(
                "page_analyser.requests.get",
                return_value=_make_http_response(status_code=404),
            ),
            patch("page_analyser.OpenAI") as mock_openai_cls,
        ):
            with pytest.raises(PageFetchError) as exc_info:
                analyse_page(_TARGET_URL)
        assert _TARGET_URL in str(exc_info.value)
        assert "404" in str(exc_info.value)
        mock_openai_cls.return_value.chat.completions.create.assert_not_called()

    def test_raises_page_fetch_error_on_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        with (
            patch(
                "page_analyser.requests.get",
                return_value=_make_http_response(status_code=500),
            ),
            patch("page_analyser.OpenAI") as mock_openai_cls,
        ):
            with pytest.raises(PageFetchError) as exc_info:
                analyse_page(_TARGET_URL)
        assert _TARGET_URL in str(exc_info.value)
        assert "500" in str(exc_info.value)
        mock_openai_cls.return_value.chat.completions.create.assert_not_called()

    def test_returns_string_le_900_chars_on_200(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        long_content = "z" * 1000
        with (
            patch("page_analyser.requests.get", return_value=_make_http_response()),
            patch("page_analyser.OpenAI") as mock_openai_cls,
        ):
            mock_openai_cls.return_value.chat.completions.create.return_value = (
                _make_openai_completion(long_content)
            )
            result = analyse_page(_TARGET_URL)
        assert isinstance(result, str)
        assert len(result) <= 900


# ---------------------------------------------------------------------------
# Tests: OpenAI prompt content
# ---------------------------------------------------------------------------


class TestAnalysePagePromptContent:
    def _capture_prompt(
        self, monkeypatch: pytest.MonkeyPatch, html: str
    ) -> str:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        captured: list[str] = []

        def fake_create(**kwargs):
            for msg in kwargs.get("messages", []):
                captured.append(msg["content"])
            return _make_openai_completion("result")

        with (
            patch("page_analyser.requests.get", return_value=_make_http_response(text=html)),
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


# ---------------------------------------------------------------------------
# Tests: 900-character truncation
# ---------------------------------------------------------------------------


class TestAnalysePageTruncation:
    def test_short_response_returned_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        short_desc = "x" * 500
        with (
            patch("page_analyser.requests.get", return_value=_make_http_response()),
            patch("page_analyser.OpenAI") as mock_openai_cls,
        ):
            mock_openai_cls.return_value.chat.completions.create.return_value = (
                _make_openai_completion(short_desc)
            )
            result = analyse_page(_TARGET_URL)
        assert result == short_desc

    def test_long_response_truncated_to_900_chars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        long_desc = "y" * 1200
        with (
            patch("page_analyser.requests.get", return_value=_make_http_response()),
            patch("page_analyser.OpenAI") as mock_openai_cls,
        ):
            mock_openai_cls.return_value.chat.completions.create.return_value = (
                _make_openai_completion(long_desc)
            )
            result = analyse_page(_TARGET_URL)
        assert len(result) == 900
