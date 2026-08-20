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
        source_url: str | None = None,
    ) -> int:
        """Download dataset results and persist them as an envelope JSON file.

        The existing file at *output_path* (if any) is first rotated to
        ``previous.json`` in the same directory so that the diff engine can
        compare the two snapshots.

        Args:
            dataset_id: The ready dataset ID to download.
            output_path: Destination path for the envelope JSON file.
            source_url: The URL that was scraped. Written into meta and used as
                fallback source_url on individual records. Defaults to the
                collector's configured default URL.

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

        effective_source_url = source_url or _DEFAULT_TARGET_URL
        meta: dict[str, Any] = {
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_url": effective_source_url,
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
        # "product_page_url".
        #
        # Field remapping: the demo collector uses different field names from the
        # canonical schema (e.g. current_price vs cmp, dividend_yield vs
        # dividend_yield_pct). We remap here so health_check passes regardless
        # of what field names the self-heal refactor leaves behind.
        if "company_name" in first and "product_page_url" not in first:
            scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            normalised = []
            for r in raw:
                name = r.get("company_name", "")
                synthetic_ticker = name.upper().replace(" ", "_")[:20]

                # Parse numeric fields that Bright Data may return as strings or
                # Money objects (serialised as {"amount": ..., "currency": ...}).
                def _num(val: Any) -> float | None:
                    if val is None:
                        return None
                    if isinstance(val, (int, float)):
                        return float(val)
                    if isinstance(val, dict):
                        # Bright Data Money objects serialise as {"value": ..., "currency": ...}
                        return float(val.get("value") or val.get("amount") or 0)
                    try:
                        return float(str(val).replace(",", ""))
                    except (ValueError, TypeError):
                        return None

                normalised.append({
                    "ticker": synthetic_ticker,
                    "company_name": name,
                    # canonical name for current market price
                    "cmp": _num(r.get("current_price") or r.get("cmp")),
                    # canonical name for dividend yield
                    "dividend_yield_pct": _num(r.get("dividend_yield") or r.get("dividend_yield_pct")),
                    "pe_ratio": _num(r.get("pe_ratio")),
                    "market_cap_cr": _num(r.get("market_cap") or r.get("market_cap_cr")),
                    "roce_pct": _num(r.get("roce") or r.get("roce_pct")),
                    "roe_pct": _num(r.get("roe") or r.get("roe_pct")),
                    "sales_growth_pct": _num(r.get("sales_growth_3yrs") or r.get("sales_growth_pct")),
                    # required by schema but not present in demo collector output
                    "scraped_at": r.get("scraped_at", scraped_at),
                    "source_url": r.get("source_url") or _DEFAULT_TARGET_URL,
                })
            logger.info(
                "Demo mirror format detected — normalised %d record(s) with field remapping.",
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
            RefactorError: if the API returns a non-2xx status after all retries.
        """
        _MAX_RETRIES = 3
        _RETRY_DELAY = 10  # seconds between retries on 5xx errors

        for attempt in range(1, _MAX_RETRIES + 1):
            response = self._session.post(
                f"{_BASE_URL}/dca/collectors/{self._collector_id}/refactor_template",
                json={"prompt": prompt},
            )

            if response.ok:
                break

            is_server_error = response.status_code >= 500
            if is_server_error and attempt < _MAX_RETRIES:
                logger.warning(
                    "refactor_template HTTP %d on attempt %d/%d — retrying in %ds: %s",
                    response.status_code,
                    attempt,
                    _MAX_RETRIES,
                    _RETRY_DELAY,
                    response.text[:200],
                )
                time.sleep(_RETRY_DELAY)
                continue

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

    def poll_refactor(self, job_id: str, timeout: int = 300) -> dict[str, Any]:
        """Poll the refactor progress endpoint until a terminal status is reached.

        Args:
            job_id: The job ID returned by refactor_template.
            timeout: Maximum seconds to wait before raising TimeoutError.

        Returns:
            The full progress response dict, which includes ``status``,
            ``preview_result`` (the output Bright Data's AI produced when it
            tested the generated code against the live page), and ``diff``
            (template_a = old code, template_b = proposed new code).

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

            data = response.json()
            status: str = data.get("status", "")
            logger.info(
                "poll_refactor job_id=%s status=%s elapsed=%.0fs",
                job_id,
                status,
                elapsed,
            )

            if status in _TERMINAL:
                logger.info("Refactor job %s reached status '%s'", job_id, status)
                return data

            time.sleep(_POLL_INTERVAL)

    def approve_refactor(self, job_id: str, progress: dict[str, Any]) -> None:
        """Approve a pending refactor rewrite so Bright Data saves the changes.

        Validates ``preview_result`` from the progress response before approving.
        If Bright Data's AI tested its generated code against the page and got
        zero records back, the proposed code is broken — we raise ``RefactorError``
        rather than saving a template that is known to be wrong.

        Args:
            job_id: The job ID returned by refactor_template.
            progress: The full dict returned by poll_refactor.

        Raises:
            RefactorError: if preview_result is empty or the API returns non-2xx.
        """
        preview = progress.get("preview_result") or []
        records = []
        if preview:
            first = preview[0]
            if isinstance(first, dict):
                # Nested {"stocks": [...]} format
                records = first.get("stocks") or []
                if isinstance(records, list) and records:
                    # Filter out Bright Data's "N more items" string sentinel
                    records = [r for r in records if isinstance(r, dict)]
            elif isinstance(first, list):
                records = first

        if not records:
            raise RefactorError(
                f"Refusing to approve refactor job {job_id}: "
                f"preview_result shows 0 records — generated code is broken. "
                f"preview={preview!r}"
            )

        logger.info(
            "Refactor job %s preview looks good (%d record(s)) — approving.",
            job_id,
            len(records),
        )

        response = self._session.post(
            f"{_BASE_URL}/dca/collectors/{self._collector_id}/resume_automation_job",
            json={"message": True, "auto_save": True},
        )

        if not response.ok:
            raise RefactorError(
                f"approve_refactor failed with HTTP {response.status_code}: {response.text}"
            )

        logger.info("Refactor job %s approved and saved.", job_id)
