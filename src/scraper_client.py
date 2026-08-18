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


class ConfigurationError(Exception):
    """Raised when required environment variables are missing."""


class TriggerError(Exception):
    """Raised when the /dca/trigger endpoint returns a non-2xx response."""


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
        body: dict[str, Any] = {}
        if target_url is not None:
            body["url"] = target_url

        triggered_at = datetime.now(timezone.utc).isoformat()
        logger.info("Triggering collector %s at %s", self._collector_id, triggered_at)

        response = self._session.post(
            f"{_BASE_URL}/dca/trigger",
            params=params,
            json=body if body else None,
        )

        if not response.ok:
            raise TriggerError(
                f"Trigger failed with HTTP {response.status_code}: {response.text}"
            )

        data = response.json()
        dataset_id: str = data.get("dataset_id") or data.get("id") or ""
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
        last_status = "unknown"

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Dataset {dataset_id} not ready after {elapsed:.0f}s "
                    f"(last status: {last_status})"
                )

            response = self._session.get(
                f"{_BASE_URL}/dca/dataset",
                params={"id": dataset_id},
            )
            response.raise_for_status()

            data = response.json()
            last_status = data.get("status", "unknown")
            logger.debug(
                "dataset_id=%s status=%s elapsed=%.0fs",
                dataset_id,
                last_status,
                elapsed,
            )

            if last_status == "ready":
                logger.info("Dataset %s is ready (%.0fs)", dataset_id, elapsed)
                return dataset_id

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
                "source_url": "https://www.screener.in/screens/dividend-yield/",
                "collector_id": self._collector_id,
                "record_count": len(records),
            },
            "records": records,
        }

        with open(out, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, indent=2, ensure_ascii=False)

        logger.info("Wrote %d record(s) to %s", len(records), out)
        return len(records)
