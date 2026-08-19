"""Bright Data Scraper Studio API client for Screener.in data collection."""

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.brightdata.com"
_DEFAULT_TARGET_URL = "https://www.screener.in/screens/3/highest-dividend-yield-shares/"


class ConfigurationError(Exception):
    """Raised when required environment variables are missing."""


class TriggerError(Exception):
    """Raised when the /dca/trigger endpoint returns a non-2xx response."""


class RefactorError(Exception):
    """Raised when a refactor API call returns a non-2xx response."""


class BrightDataClient:
    """Client for the Bright Data Scraper Studio Data Collector API."""

    def __init__(self) -> None:
        token = os.environ.get("BRIGHT_DATA_API_TOKEN")
        collector_id = os.environ.get("BRIGHT_DATA_COLLECTOR_ID")

        if not token:
            raise ConfigurationError(
                "BRIGHT_DATA_API_TOKEN is not set in the environment."
            )
        if not collector_id:
            raise ConfigurationError(
                "BRIGHT_DATA_COLLECTOR_ID is not set in the environment."
            )

        self._token = token
        self._collector_id = collector_id
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self._token}"

    def trigger_run(self, target_url: str | None = None) -> str:
        """Trigger a collector run and return the dataset ID.

        Args:
            target_url: Optional URL override for the collector's target.
                When None the collector uses its configured default URL.

        Returns:
            The dataset ID string returned by the API.

        Raises:
            TriggerError: if the API returns a non-2xx status.
        """
        params: dict[str, str] = {"collector": self._collector_id}
        body: dict[str, Any] = {"url": target_url or _DEFAULT_TARGET_URL}

        triggered_at = datetime.now(timezone.utc).isoformat()
        logger.info("Triggering collector %s at %s", self._collector_id, triggered_at)

        response = self._session.post(
            f"{_BASE_URL}/dca/trigger",
            params=params,
            json=body,
        )

        if not response.ok:
            raise TriggerError(
                f"Trigger failed with HTTP {response.status_code}: {response.text}"
            )

        data = response.json()
        dataset_id: str = (
            data.get("dataset_id") or data.get("collection_id") or data.get("id") or ""
        )
        if not dataset_id:
            raise TriggerError(
                f"API did not return a dataset_id. Response body: {response.text}"
            )

        logger.info("Triggered run — dataset_id=%s", dataset_id)
        return dataset_id

    def poll_until_ready(
        self,
        dataset_id: str,
        poll_interval: int = 5,
        timeout: int = 300,
    ) -> str:
        """Poll the dataset endpoint until status is 'ready'.

        Args:
            dataset_id: The dataset ID returned by trigger_run.
            poll_interval: Seconds to wait between poll requests.
            timeout: Maximum seconds to wait before raising TimeoutError.

        Returns:
            The dataset_id once the dataset is ready.

        Raises:
            TimeoutError: if the dataset is not ready within `timeout` seconds.
        """
        start = time.monotonic()
        consecutive_parse_errors = 0

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Dataset {dataset_id} not ready after {elapsed:.0f}s"
                )

            response = self._session.get(
                f"{_BASE_URL}/dca/dataset",
                params={"id": dataset_id, "format": "json"},
            )
            response.raise_for_status()

            if response.status_code == 200:
                logger.info(
                    "dataset_id=%s status=http_200_ready elapsed=%.0fs",
                    dataset_id,
                    elapsed,
                )
                return dataset_id

            # HTTP 202: still building — read status from body when available
            try:
                data = response.json()
                consecutive_parse_errors = 0
                status = data.get("status", "building")
            except ValueError:
                consecutive_parse_errors += 1
                if consecutive_parse_errors >= 2:
                    raise ValueError(
                        f"Dataset {dataset_id} returned unparseable body "
                        f"for {consecutive_parse_errors} consecutive polls"
                    )
                status = "building"

            logger.info(
                "dataset_id=%s status=%s elapsed=%.0fs",
                dataset_id,
                status,
                elapsed,
            )

            time.sleep(poll_interval)

    def download_results(
        self,
        dataset_id: str,
        output_path: str = "data/latest.json",
    ) -> int:
        """Download dataset results and persist them as an envelope JSON file.

        The existing file at *output_path* (if any) is first rotated to
        ``previous.json`` in the same directory so that the diff engine can
        compare the two snapshots.

        Args:
            dataset_id: The ready dataset ID to download.
            output_path: Destination path for the envelope JSON file.

        Returns:
            The number of records written.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Rotate existing snapshot before overwriting.
        if out.exists():
            previous = out.parent / "previous.json"
            shutil.copy2(out, previous)
            logger.info("Rotated %s → %s", out, previous)

        response = self._session.get(
            f"{_BASE_URL}/dca/dataset",
            params={"id": dataset_id, "format": "json"},
        )
        response.raise_for_status()

        raw: list[dict[str, Any]] = response.json()
        if not isinstance(raw, list):
            raw = []

        records = self._normalize_records(raw)

        # Extract a sample company URL for self-heal page analysis when all
        # records are skipped due to empty stock_results.
        sample_company_url: str | None = None
        if not records and raw:
            sample_company_url = next(
                (r.get("product_page_url") for r in raw if r.get("product_page_url")),
                None,
            )
            logger.warning(
                "Dataset %s: %d raw record(s) fetched but 0 valid after normalisation. "
                "screener.in page structure may have changed — self-heal should trigger.",
                dataset_id,
                len(raw),
            )
        elif not records:
            logger.warning("Dataset %s returned an empty result set.", dataset_id)

        meta: dict[str, Any] = {
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_url": _DEFAULT_TARGET_URL,
            "collector_id": self._collector_id,
            "record_count": len(records),
        }
        if sample_company_url:
            meta["sample_company_url"] = sample_company_url

        envelope: dict[str, Any] = {"meta": meta, "records": records}

        with open(out, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, indent=2, ensure_ascii=False)

        logger.info("Wrote %d record(s) to %s", len(records), out)
        return len(records)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_records(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Bright Data's raw API response to our canonical record schema.

        Bright Data's collector returns records in one of four formats:

        **Canonical** (already has ``ticker`` and financial fields):
        Returned as-is with no transformation.

        **URL-based** (collector found company pages but scraped them separately):
        Each record has ``product_page_url``, ``stock_results``, and ``input``.
        ``stock_results`` holds the actual financial data extracted from the
        company page — when it is empty the scrape failed (page structure changed).
        Only records with non-empty ``stock_results`` are kept; empty ones are
        dropped so that ``record_count`` correctly reflects usable data and the
        self-heal trigger fires when needed.

        **Demo mirror — flat** (``company_name`` present, no ``ticker``/``product_page_url``):
        Produced by the demo collector after a self-heal rewrite. A synthetic
        ticker is derived from ``company_name`` so downstream code has a stable key.

        **Demo mirror — nested** (``{"stocks": [...]}`` wrapper):
        Some self-heal rewrites emit a top-level ``stocks`` array. Unwrapped and
        re-normalised recursively.

        Returns:
            List of records conforming to the canonical schema (or as close as
            the raw data allows).
        """
        if not raw:
            return raw

        first = raw[0]

        # Fast path: already canonical — strip Bright Data internal fields
        if "ticker" in first:
            _BD_INTERNAL = {"input"}
            if _BD_INTERNAL & first.keys():
                return [{k: v for k, v in r.items() if k not in _BD_INTERNAL} for r in raw]
            return raw

        # Demo mirror format: the self-heal loop rewrites the Bright Data parser
        # automatically via refactor_template, so we cannot control whether it
        # emits a flat list or a nested {"stocks": [...]} shape. We handle both
        # here so _normalize_records stays robust across self-heal cycles.
        # Records are identified by having "company_name" but no "ticker" or
        # "product_page_url". A synthetic ticker is derived from company_name so
        # downstream health_check and diff_engine have a stable identity key.
        if "company_name" in first and "product_page_url" not in first:
            normalised = []
            for r in raw:
                name = r.get("company_name", "")
                synthetic_ticker = name.upper().replace(" ", "_")[:20]
                normalised.append({"ticker": synthetic_ticker, **r})
            logger.info(
                "Demo mirror format detected — normalised %d record(s) with synthetic tickers.",
                len(normalised),
            )
            return normalised

        # Nested demo format: {"stocks": [...]} — unwrap and recurse
        if "stocks" in first and isinstance(first.get("stocks"), list):
            unwrapped = [row for r in raw for row in r.get("stocks", [])]
            logger.info(
                "Demo mirror nested format detected — unwrapped %d record(s).",
                len(unwrapped),
            )
            return self._normalize_records(unwrapped)

        # URL-based format from Bright Data's collector
        if "product_page_url" not in first:
            logger.warning(
                "Unrecognised record format from Bright Data. "
                "Top-level keys: %s. Records cannot be normalised.",
                sorted(first.keys()),
            )
            return []

        normalised: list[dict[str, Any]] = []
        skipped = 0

        for r in raw:
            stock_results = r.get("stock_results") or []
            if not stock_results:
                skipped += 1
                continue

            url = r.get("product_page_url", "")
            path_parts = [p for p in urlparse(url).path.split("/") if p]
            # Expected path: /company/{TICKER}[/consolidated]
            if len(path_parts) < 2 or path_parts[0] != "company":
                logger.warning("Cannot extract ticker from URL '%s' — skipping.", url)
                skipped += 1
                continue

            ticker = path_parts[1]
            data = stock_results[0] if isinstance(stock_results, list) else stock_results
            normalised.append({
                "ticker": ticker,
                "source_url": url,
                **data,
            })

        if skipped:
            logger.warning(
                "Skipped %d/%d record(s) with empty stock_results — "
                "screener.in company page structure may have changed.",
                skipped,
                len(raw),
            )

        return normalised

    def refactor_template(self, prompt: str) -> str:
        """Send a fix prompt to the refactor endpoint and return the job ID.

        Args:
            prompt: Natural-language description of the CSS selector fix to apply.

        Returns:
            The job ID string returned by the API.

        Raises:
            RefactorError: if the API returns a non-2xx status.
        """
        response = self._session.post(
            f"{_BASE_URL}/dca/collectors/{self._collector_id}/refactor_template",
            json={"prompt": prompt},
        )

        if not response.ok:
            raise RefactorError(
                f"refactor_template failed with HTTP {response.status_code}: {response.text}"
            )

        data = response.json()
        job_id: str = data.get("job_id") or data.get("id") or ""
        if not job_id:
            raise RefactorError(
                f"API did not return a job_id. Response body: {response.text}"
            )

        logger.info("Refactor job started — job_id=%s", job_id)
        return job_id

    def poll_refactor(self, job_id: str, timeout: int = 300) -> str:
        """Poll the refactor progress endpoint until a terminal status is reached.

        Args:
            job_id: The job ID returned by refactor_template.
            timeout: Maximum seconds to wait before raising TimeoutError.

        Returns:
            The terminal status string: ``"done"`` or ``"pending_answer"``.

        Raises:
            TimeoutError: if neither terminal status is reached within `timeout` seconds.
        """
        _POLL_INTERVAL = 5
        _TERMINAL = {"done", "pending_answer"}

        start = time.monotonic()
        url = f"{_BASE_URL}/dca/collectors/{self._collector_id}/refactor_template/progress"

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Refactor job {job_id} did not reach a terminal status "
                    f"after {elapsed:.0f}s"
                )

            response = self._session.get(url)
            response.raise_for_status()

            status: str = response.json().get("status", "")
            logger.info(
                "poll_refactor job_id=%s status=%s elapsed=%.0fs",
                job_id,
                status,
                elapsed,
            )

            if status in _TERMINAL:
                logger.info("Refactor job %s reached status '%s'", job_id, status)
                return status

            time.sleep(_POLL_INTERVAL)

    def approve_refactor(self, job_id: str) -> None:
        """Approve a pending refactor rewrite so Bright Data saves the changes.

        Args:
            job_id: The job ID returned by refactor_template.

        Raises:
            RefactorError: if the API returns a non-2xx status.
        """
        response = self._session.post(
            f"{_BASE_URL}/dca/collectors/{self._collector_id}/resume_automation_job",
            json={"message": True, "auto_save": True},
        )

        if not response.ok:
            raise RefactorError(
                f"approve_refactor failed with HTTP {response.status_code}: {response.text}"
            )

        logger.info("Refactor job %s approved and saved.", job_id)
