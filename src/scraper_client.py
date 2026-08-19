"""Bright Data Scraper Studio API client for Screener.in data collection."""

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

        records: list[dict[str, Any]] = response.json()
        if not isinstance(records, list):
            records = []

        if not records:
            logger.warning("Dataset %s returned an empty result set.", dataset_id)

        envelope: dict[str, Any] = {
            "meta": {
                "scraped_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "source_url": _DEFAULT_TARGET_URL,
                "collector_id": self._collector_id,
                "record_count": len(records),
            },
            "records": records,
        }

        with open(out, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, indent=2, ensure_ascii=False)

        logger.info("Wrote %d record(s) to %s", len(records), out)
        return len(records)

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
