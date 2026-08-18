"""Tests for src/scraper_client.py — ConfigurationError and mocked API calls."""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scraper_client import (  # noqa: E402
    BrightDataClient,
    ConfigurationError,
    TriggerError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENV_TOKEN = "test-api-token"
_ENV_COLLECTOR = "c_testcollector123"


def _make_env(**overrides) -> dict:
    env = {
        "BRIGHT_DATA_API_TOKEN": _ENV_TOKEN,
        "BRIGHT_DATA_COLLECTOR_ID": _ENV_COLLECTOR,
    }
    env.update(overrides)
    return env


def _make_response(status_code: int = 200, json_data=None, text: str = "") -> Mock:
    resp = Mock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.text = text if text else json.dumps(json_data or {})
    resp.json.return_value = json_data if json_data is not None else {}
    resp.raise_for_status = Mock(
        side_effect=(
            None
            if 200 <= status_code < 300
            else Exception(f"HTTP {status_code}")
        )
    )
    return resp


# ---------------------------------------------------------------------------
# Tests: __init__ — ConfigurationError
# ---------------------------------------------------------------------------


class TestInit:
    def test_raises_when_token_missing(self) -> None:
        env = {"BRIGHT_DATA_COLLECTOR_ID": _ENV_COLLECTOR}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                BrightDataClient()
        assert "BRIGHT_DATA_API_TOKEN" in str(exc_info.value)

    def test_raises_when_collector_id_missing(self) -> None:
        env = {"BRIGHT_DATA_API_TOKEN": _ENV_TOKEN}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                BrightDataClient()
        assert "BRIGHT_DATA_COLLECTOR_ID" in str(exc_info.value)

    def test_raises_when_both_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError):
                BrightDataClient()

    def test_no_error_when_both_present(self) -> None:
        with patch.dict(os.environ, _make_env(), clear=True):
            client = BrightDataClient()
        assert client is not None


# ---------------------------------------------------------------------------
# Tests: trigger_run
# ---------------------------------------------------------------------------


class TestTriggerRun:
    def _client(self) -> BrightDataClient:
        with patch.dict(os.environ, _make_env(), clear=True):
            return BrightDataClient()

    def test_returns_dataset_id_on_success(self) -> None:
        client = self._client()
        mock_resp = _make_response(200, {"dataset_id": "ds_abc123"})

        with patch.object(client._session, "post", return_value=mock_resp) as mock_post:
            dataset_id = client.trigger_run()

        assert dataset_id == "ds_abc123"
        mock_post.assert_called_once()

    def test_posts_to_correct_endpoint(self) -> None:
        client = self._client()
        mock_resp = _make_response(200, {"dataset_id": "ds_abc123"})

        with patch.object(client._session, "post", return_value=mock_resp) as mock_post:
            client.trigger_run()

        call_args = mock_post.call_args
        assert "/dca/trigger" in call_args.args[0]

    def test_includes_collector_id_in_params(self) -> None:
        client = self._client()
        mock_resp = _make_response(200, {"dataset_id": "ds_abc123"})

        with patch.object(client._session, "post", return_value=mock_resp) as mock_post:
            client.trigger_run()

        params = mock_post.call_args.kwargs.get("params", {})
        assert params.get("collector") == _ENV_COLLECTOR

    def test_uses_custom_target_url_when_provided(self) -> None:
        client = self._client()
        mock_resp = _make_response(200, {"dataset_id": "ds_abc123"})
        custom_url = "https://example.com/custom"

        with patch.object(client._session, "post", return_value=mock_resp) as mock_post:
            client.trigger_run(target_url=custom_url)

        body = mock_post.call_args.kwargs.get("json", {})
        assert body.get("url") == custom_url

    def test_raises_trigger_error_on_non_2xx(self) -> None:
        client = self._client()
        mock_resp = _make_response(401, text="Unauthorized")
        mock_resp.ok = False

        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(TriggerError):
                client.trigger_run()

    def test_raises_trigger_error_when_no_dataset_id_in_response(self) -> None:
        client = self._client()
        mock_resp = _make_response(200, {"message": "triggered"})  # no dataset_id

        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(TriggerError):
                client.trigger_run()

    def test_accepts_collection_id_key_as_dataset_id(self) -> None:
        client = self._client()
        mock_resp = _make_response(200, {"collection_id": "ds_col123"})

        with patch.object(client._session, "post", return_value=mock_resp):
            dataset_id = client.trigger_run()

        assert dataset_id == "ds_col123"


# ---------------------------------------------------------------------------
# Tests: poll_until_ready
# ---------------------------------------------------------------------------


class TestPollUntilReady:
    def _client(self) -> BrightDataClient:
        with patch.dict(os.environ, _make_env(), clear=True):
            return BrightDataClient()

    def test_returns_dataset_id_when_status_is_ready(self) -> None:
        client = self._client()
        mock_resp = _make_response(200, {"status": "ready"})

        with patch.object(client._session, "get", return_value=mock_resp):
            with patch("time.sleep"):
                result = client.poll_until_ready("ds_abc123", poll_interval=0)

        assert result == "ds_abc123"

    def test_retries_until_ready(self) -> None:
        client = self._client()
        pending_resp = _make_response(200, {"status": "running"})
        ready_resp = _make_response(200, {"status": "ready"})

        with patch.object(
            client._session, "get", side_effect=[pending_resp, pending_resp, ready_resp]
        ):
            with patch("time.sleep"):
                result = client.poll_until_ready("ds_abc123", poll_interval=0)

        assert result == "ds_abc123"

    def test_raises_timeout_error_when_not_ready_in_time(self) -> None:
        client = self._client()
        pending_resp = _make_response(200, {"status": "running"})

        call_count = 0

        def _fake_monotonic():
            nonlocal call_count
            call_count += 1
            # Simulate time advancing fast: first call returns 0, subsequent ones exceed timeout
            return 0.0 if call_count == 1 else 400.0

        with patch.object(client._session, "get", return_value=pending_resp):
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=_fake_monotonic):
                    with pytest.raises(TimeoutError):
                        client.poll_until_ready("ds_abc123", timeout=300, poll_interval=0)

    def test_handles_empty_response_body_gracefully(self) -> None:
        client = self._client()
        empty_resp = _make_response(200)
        empty_resp.json.side_effect = ValueError("No JSON")
        ready_resp = _make_response(200, {"status": "ready"})

        with patch.object(
            client._session, "get", side_effect=[empty_resp, ready_resp]
        ):
            with patch("time.sleep"):
                result = client.poll_until_ready("ds_abc123", poll_interval=0)

        assert result == "ds_abc123"


# ---------------------------------------------------------------------------
# Tests: download_results
# ---------------------------------------------------------------------------


class TestDownloadResults:
    def _client(self) -> BrightDataClient:
        with patch.dict(os.environ, _make_env(), clear=True):
            return BrightDataClient()

    _SAMPLE_RECORDS = [
        {
            "company_name": "Alpha Corp",
            "ticker": "ALPHA",
            "exchange": "NSE",
            "cmp": 100.0,
            "dividend_yield_pct": 3.5,
            "scraped_at": "2024-06-15T10:00:00Z",
            "source_url": "https://www.screener.in/screens/dividend-yield/",
        }
    ]

    def test_writes_envelope_json_file(self, tmp_path: Path) -> None:
        client = self._client()
        output_path = str(tmp_path / "latest.json")
        mock_resp = _make_response(200, self._SAMPLE_RECORDS)

        with patch.object(client._session, "get", return_value=mock_resp):
            count = client.download_results("ds_abc123", output_path=output_path)

        assert count == 1
        with open(output_path, encoding="utf-8") as fh:
            envelope = json.load(fh)

        assert "meta" in envelope
        assert "records" in envelope
        assert envelope["meta"]["record_count"] == 1
        assert len(envelope["records"]) == 1

    def test_rotates_existing_file_to_previous(self, tmp_path: Path) -> None:
        client = self._client()
        output_path = tmp_path / "latest.json"
        # Pre-populate latest.json
        output_path.write_text(json.dumps({"meta": {}, "records": []}), encoding="utf-8")
        mock_resp = _make_response(200, self._SAMPLE_RECORDS)

        with patch.object(client._session, "get", return_value=mock_resp):
            client.download_results("ds_abc123", output_path=str(output_path))

        previous = tmp_path / "previous.json"
        assert previous.exists()

    def test_returns_zero_for_empty_dataset(self, tmp_path: Path) -> None:
        client = self._client()
        output_path = str(tmp_path / "latest.json")
        mock_resp = _make_response(200, [])

        with patch.object(client._session, "get", return_value=mock_resp):
            count = client.download_results("ds_abc123", output_path=output_path)

        assert count == 0

    def test_meta_record_count_matches_records_length(self, tmp_path: Path) -> None:
        client = self._client()
        records = self._SAMPLE_RECORDS * 3
        output_path = str(tmp_path / "latest.json")
        mock_resp = _make_response(200, records)

        with patch.object(client._session, "get", return_value=mock_resp):
            client.download_results("ds_abc123", output_path=output_path)

        with open(output_path, encoding="utf-8") as fh:
            envelope = json.load(fh)

        assert envelope["meta"]["record_count"] == len(envelope["records"])
