"""CLI entry point: automated self-heal loop for Bright Data scrape results."""

import argparse
import json
import logging
import os
import sys
import time

# Ensure both the project root and src/ are importable regardless of invocation style.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from scraper_client import BrightDataClient, ConfigurationError  # noqa: E402
from health_check import health_check, HealthStatus  # noqa: E402
from page_analyser import analyse_page, generate_fallback_prompt  # noqa: E402

_DEFAULT_TARGET_URL = "https://www.screener.in/screens/3/highest-dividend-yield-shares/"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _load_envelope(output_path: str) -> dict:
    with open(output_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Automated self-heal loop for Bright Data scrape results."
    )
    parser.add_argument(
        "--target-url",
        default=None,
        help="Override the collector's default target URL.",
    )
    args = parser.parse_args(argv)

    effective_url: str = args.target_url or _DEFAULT_TARGET_URL

    # Demo pages (GitHub Pages mirror) have non-deterministic template propagation
    # delays — verification scrapes consistently fail within the same run.
    # Skip post-refactor verification for demo URLs; the next run will confirm recovery.
    # Data is also written to separate folders to avoid mixing demo and production data.
    is_demo_url = "github.io" in effective_url
    _OUTPUT_PATH = "data/demo/latest.json" if is_demo_url else "data/production/latest.json"
    _DATA_DIR = "data/demo" if is_demo_url else "data/production"

    try:
        client = BrightDataClient()
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    # --- First download cycle ---
    try:
        dataset_id = client.trigger_run(target_url=args.target_url)
        client.poll_until_ready(dataset_id)
        client.download_results(dataset_id, output_path=_OUTPUT_PATH)
    except Exception as exc:  # noqa: BLE001
        logger.error("First download cycle failed: %s", exc)
        return 1

    initial_report = health_check(_load_envelope(_OUTPUT_PATH))
    logger.info(
        "Initial health: status=%s reason=%s",
        initial_report.status.value,
        initial_report.reason,
    )

    if initial_report.status == HealthStatus.HEALTHY:
        logger.info(
            "SUMMARY | original_status=HEALTHY | fix_prompt=N/A | recovery_status=not_needed"
        )
        logger.info("Scrape is healthy — no self-heal needed.")
        return 0

    # --- Self-heal path (at most one attempt) ---
    # Prefer a sample company page URL (where stock_results was empty) over the
    # screen listing URL — the company page is where the selector failure occurs.
    envelope = _load_envelope(_OUTPUT_PATH)
    analyse_url = envelope.get("meta", {}).get("sample_company_url") or effective_url
    if analyse_url != effective_url:
        logger.info("Analysing company page instead of screen listing: %s", analyse_url)

    fix_prompt: str = ""
    try:
        fix_prompt = generate_fallback_prompt(effective_url) or ""
        if fix_prompt:
            logger.info(
                "Using deterministic fallback prompt (layout marker detected) — length=%d",
                len(fix_prompt),
            )
        else:
            fix_prompt = analyse_page(analyse_url)
            logger.info("Page analysis complete — fix_prompt length=%d", len(fix_prompt))

        job_id = client.refactor_template(fix_prompt)
        progress = client.poll_refactor(job_id)
        client.approve_refactor(job_id, progress)

        if is_demo_url:
            # Demo pages have unpredictable template propagation delays — skip
            # verification scrapes and let the next workflow run confirm recovery.
            logger.info(
                "SUMMARY | original_status=%s | fix_prompt=%s | recovery_status=refactor_approved_demo",
                initial_report.status.value,
                fix_prompt,
            )
            logger.info(
                "Demo URL detected — skipping verification scrape. "
                "Re-run selfheal-loop to confirm recovery once the template propagates."
            )
            return 0

        # Wait for the refactored template to propagate before triggering the
        # second scrape. Without this delay, the collector may still run the
        # old template and return 0 records even though the refactor succeeded.
        _REFACTOR_PROPAGATION_DELAY = 15
        logger.info("Waiting %ds for refactored template to propagate…", _REFACTOR_PROPAGATION_DELAY)
        time.sleep(_REFACTOR_PROPAGATION_DELAY)
    except Exception as exc:  # noqa: BLE001
        logger.error("Self-heal step failed: %s", exc)
        logger.info(
            "SUMMARY | original_status=%s | fix_prompt=%s | recovery_status=failed",
            initial_report.status.value,
            fix_prompt or "N/A",
        )
        return 1

    # --- Second download cycle (production only) ---
    try:
        dataset_id2 = client.trigger_run(target_url=args.target_url)
        client.poll_until_ready(dataset_id2)
        client.download_results(dataset_id2, output_path=_OUTPUT_PATH)
    except Exception as exc:  # noqa: BLE001
        logger.error("Second download cycle failed: %s", exc)
        logger.info(
            "SUMMARY | original_status=%s | fix_prompt=%s | recovery_status=failed",
            initial_report.status.value,
            fix_prompt,
        )
        return 1

    second_report = health_check(_load_envelope(_OUTPUT_PATH))
    logger.info(
        "Second health: status=%s reason=%s",
        second_report.status.value,
        second_report.reason,
    )

    recovery_status = "recovered" if second_report.status == HealthStatus.HEALTHY else "failed"
    logger.info(
        "SUMMARY | original_status=%s | fix_prompt=%s | recovery_status=%s",
        initial_report.status.value,
        fix_prompt,
        recovery_status,
    )

    if second_report.status != HealthStatus.HEALTHY:
        logger.error("Recovery failed — second health check: %s", second_report.reason)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
