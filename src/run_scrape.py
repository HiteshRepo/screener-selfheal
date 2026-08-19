"""CLI entry point: trigger → poll → download a Bright Data scrape run."""

import argparse
import logging
import sys

from scraper_client import BrightDataClient, ConfigurationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Bright Data scrape job.")
    parser.add_argument(
        "--url",
        default=None,
        help="Override the collector's default target URL.",
    )
    parser.add_argument(
        "--output",
        default="data/latest.json",
        help="Output path for the envelope JSON (default: data/latest.json).",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Seconds between status polls (default: 5).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Max seconds to wait for dataset ready (default: 900).",
    )
    args = parser.parse_args(argv)

    try:
        client = BrightDataClient()
    except ConfigurationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        dataset_id = client.trigger_run(target_url=args.url)
        client.poll_until_ready(
            dataset_id,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        count = client.download_results(dataset_id, output_path=args.output)
    except (TimeoutError, Exception) as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Scrape complete — {count} record(s) written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
