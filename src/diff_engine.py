"""Data diff engine for comparing Screener.in scrape snapshots."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Default thresholds for classifying a ticker as CHANGED.
_DEFAULT_THRESHOLDS: dict[str, float] = {
    "dividend_yield_pct": 0.5,  # absolute percentage points
    "cmp": 0.05,                # 5% relative change (stored as fraction)
    "pe_ratio": 2.0,            # absolute change
}

# Fields inspected during diff; all others ignored.
_TRACKED_FIELDS: list[str] = [
    "dividend_yield_pct",
    "cmp",
    "pe_ratio",
    "market_cap_cr",
    "roce_pct",
    "roe_pct",
    "sales_growth_pct",
]


@dataclass
class FieldDelta:
    """A single field change between two snapshots."""

    field: str
    old_value: float | None
    new_value: float | None


@dataclass
class TickerChange:
    """Classification result for one ticker."""

    ticker: str
    company_name: str
    status: str          # ENTERED | EXITED | CHANGED | UNCHANGED
    record: dict
    deltas: list[FieldDelta] = field(default_factory=list)


@dataclass
class DiffResult:
    """Aggregated classification of all tickers across two snapshots."""

    entered: list[TickerChange]
    exited: list[TickerChange]
    changed: list[TickerChange]
    unchanged: list[TickerChange]
    is_first_run: bool
    snapshot_date: str   # YYYY-MM-DD derived from the latest snapshot


class DiffEngine:
    """Compares two Screener.in scrape snapshots and classifies changes."""

    def load_snapshots(
        self,
        latest_path: str,
        previous_path: str,
    ) -> tuple[list[dict], list[dict]]:
        """Load both JSON envelopes and return their record lists.

        Args:
            latest_path: Path to the latest snapshot envelope JSON.
            previous_path: Path to the previous snapshot envelope JSON.

        Returns:
            (latest_records, previous_records). previous_records is an empty
            list when the file does not exist.
        """
        latest_records = self._load_records(latest_path)

        prev = Path(previous_path)
        if not prev.exists():
            logger.info(
                "No previous snapshot at %s — treating run as first run.", prev
            )
            return latest_records, []

        previous_records = self._load_records(previous_path)
        return latest_records, previous_records

    # Candidate field names for the ticker symbol, in priority order.
    _TICKER_ALIASES: list[str] = [
        "ticker",
        "symbol",
        "stock_symbol",
        "nse_code",
        "bse_code",
        "scrip_code",
        "scrip",
        "nse_symbol",
        "bse_symbol",
    ]

    def _load_records(self, path: str) -> list[dict]:
        with open(path, encoding="utf-8") as fh:
            envelope = json.load(fh)
        records: list[dict] = envelope.get("records", [])
        return self._normalize_records(records)

    def _normalize_records(self, records: list[dict]) -> list[dict]:
        """Ensure every record has a ``ticker`` key.

        Bright Data may return the ticker under a different field name.  Try
        each alias in ``_TICKER_ALIASES`` in order.  Records that cannot be
        normalised are dropped with a warning so the diff can still proceed.
        """
        if not records:
            return records

        # Detect the alias used in this batch (check only the first record).
        first = records[0]
        if "ticker" in first:
            return records  # already canonical — fast path

        alias = next(
            (a for a in self._TICKER_ALIASES if a in first),
            None,
        )
        if alias is None:
            logger.warning(
                "No recognised ticker field found in scraped records. "
                "Known keys: %s. Records will be skipped.",
                list(first.keys()),
            )
            return []

        logger.info(
            "Normalising ticker field from '%s' → 'ticker' for %d record(s).",
            alias,
            len(records),
        )
        normalised: list[dict] = []
        for r in records:
            if alias not in r:
                logger.warning("Record missing '%s' field — skipping: %s", alias, r)
                continue
            normalised.append({**r, "ticker": r[alias]})
        return normalised

    def diff(
        self,
        latest: list[dict],
        previous: list[dict],
        thresholds: dict | None = None,
    ) -> DiffResult:
        """Classify each ticker as ENTERED / EXITED / CHANGED / UNCHANGED.

        Args:
            latest: Record list from the latest snapshot.
            previous: Record list from the previous snapshot (empty → first run).
            thresholds: Optional dict overriding default change thresholds.
                Supported keys: ``dividend_yield_pct`` (absolute pp),
                ``cmp`` (relative fraction), ``pe_ratio`` (absolute).
                Any other tracked field defaults to "any non-null change".

        Returns:
            DiffResult with four categorised lists.
        """
        effective = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}
        is_first_run = len(previous) == 0

        latest_by_ticker: dict[str, dict] = {r["ticker"]: r for r in latest}
        previous_by_ticker: dict[str, dict] = {r["ticker"]: r for r in previous}

        entered: list[TickerChange] = []
        exited: list[TickerChange] = []
        changed: list[TickerChange] = []
        unchanged: list[TickerChange] = []

        for ticker, record in latest_by_ticker.items():
            if ticker not in previous_by_ticker:
                entered.append(
                    TickerChange(
                        ticker=ticker,
                        company_name=record.get("company_name", ticker),
                        status="ENTERED",
                        record=record,
                    )
                )
            else:
                old = previous_by_ticker[ticker]
                deltas = self._compute_deltas(record, old, effective)
                if deltas:
                    changed.append(
                        TickerChange(
                            ticker=ticker,
                            company_name=record.get("company_name", ticker),
                            status="CHANGED",
                            record=record,
                            deltas=deltas,
                        )
                    )
                else:
                    unchanged.append(
                        TickerChange(
                            ticker=ticker,
                            company_name=record.get("company_name", ticker),
                            status="UNCHANGED",
                            record=record,
                        )
                    )

        for ticker, record in previous_by_ticker.items():
            if ticker not in latest_by_ticker:
                exited.append(
                    TickerChange(
                        ticker=ticker,
                        company_name=record.get("company_name", ticker),
                        status="EXITED",
                        record=record,
                    )
                )

        snapshot_date = self._extract_snapshot_date(latest)

        return DiffResult(
            entered=entered,
            exited=exited,
            changed=changed,
            unchanged=unchanged,
            is_first_run=is_first_run,
            snapshot_date=snapshot_date,
        )

    def _compute_deltas(
        self,
        new: dict,
        old: dict,
        thresholds: dict[str, float],
    ) -> list[FieldDelta]:
        """Return FieldDeltas for fields that exceeded their change threshold."""
        deltas: list[FieldDelta] = []
        for f in _TRACKED_FIELDS:
            new_val = new.get(f)
            old_val = old.get(f)

            # Both null — no change
            if new_val is None and old_val is None:
                continue

            # One side is null — always flag
            if new_val is None or old_val is None:
                deltas.append(FieldDelta(field=f, old_value=old_val, new_value=new_val))
                continue

            # cmp uses relative change threshold
            if f == "cmp":
                threshold = thresholds.get("cmp", _DEFAULT_THRESHOLDS["cmp"])
                if old_val != 0 and abs(new_val - old_val) / abs(old_val) > threshold:
                    deltas.append(
                        FieldDelta(field=f, old_value=old_val, new_value=new_val)
                    )
            elif f in thresholds:
                if abs(new_val - old_val) > thresholds[f]:
                    deltas.append(
                        FieldDelta(field=f, old_value=old_val, new_value=new_val)
                    )
            else:
                # Any non-null change
                if new_val != old_val:
                    deltas.append(
                        FieldDelta(field=f, old_value=old_val, new_value=new_val)
                    )

        return deltas

    def _extract_snapshot_date(self, records: list[dict]) -> str:
        """Derive YYYY-MM-DD from the first record's scraped_at, or today."""
        for record in records:
            scraped_at = record.get("scraped_at")
            if scraped_at and len(scraped_at) >= 10:
                return scraped_at[:10]
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def write_report(
        self,
        diff_result: DiffResult,
        output_dir: str = "data",
    ) -> str:
        """Append this run's diff to a dated Markdown file.

        Prepends a ``## Run at HH:MM:SS UTC`` header and a ``---`` separator
        before each run's content when appending to an existing file.

        Args:
            diff_result: The DiffResult to render.
            output_dir: Directory for the report file.

        Returns:
            The path of the written (or appended-to) file as a string.
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        report_path = out_dir / f"changes-{diff_result.snapshot_date}.md"
        run_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
        file_exists = report_path.exists()

        lines: list[str] = []

        # Separator between runs when appending
        if file_exists:
            lines.append("---")
            lines.append("")

        lines.append(f"## Run at {run_time} UTC")
        lines.append("")

        if diff_result.is_first_run:
            lines.append(
                "> First run — no previous snapshot; all records treated as ENTERED."
            )
            lines.append("")

        if diff_result.entered:
            lines.append("### ENTERED")
            lines.append("")
            for tc in diff_result.entered:
                cmp_val = tc.record.get("cmp", "—")
                dy_val = tc.record.get("dividend_yield_pct", "—")
                lines.append(
                    f"- **{tc.company_name}** (`{tc.ticker}`) "
                    f"— CMP: ₹{cmp_val}, Div Yield: {dy_val}%"
                )
            lines.append("")

        if diff_result.exited:
            lines.append("### EXITED")
            lines.append("")
            for tc in diff_result.exited:
                cmp_val = tc.record.get("cmp", "—")
                dy_val = tc.record.get("dividend_yield_pct", "—")
                lines.append(
                    f"- **{tc.company_name}** (`{tc.ticker}`) "
                    f"— last CMP: ₹{cmp_val}, last Div Yield: {dy_val}%"
                )
            lines.append("")

        if diff_result.changed:
            lines.append("### CHANGED")
            lines.append("")
            for tc in diff_result.changed:
                lines.append(f"- **{tc.company_name}** (`{tc.ticker}`)")
                for delta in tc.deltas:
                    lines.append(
                        f"  - `{delta.field}`: {delta.old_value} → {delta.new_value}"
                    )
            lines.append("")

        n_entered = len(diff_result.entered)
        n_exited = len(diff_result.exited)
        n_changed = len(diff_result.changed)
        n_unchanged = len(diff_result.unchanged)
        lines.append(
            f"**Summary:** {n_entered} entered · {n_exited} exited · "
            f"{n_changed} changed · {n_unchanged} unchanged"
        )
        lines.append("")

        content = "\n".join(lines)
        mode = "a" if file_exists else "w"
        with open(report_path, mode, encoding="utf-8") as fh:
            fh.write(content)

        logger.info("Diff report written to %s", report_path)
        return str(report_path)
