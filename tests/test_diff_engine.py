"""Tests for src/diff_engine.py — DiffEngine classification and threshold logic."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from diff_engine import DiffEngine, DiffResult, FieldDelta, TickerChange  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_RECORD = {
    "company_name": "Alpha Corp",
    "ticker": "ALPHA",
    "exchange": "NSE",
    "cmp": 100.0,
    "dividend_yield_pct": 3.5,
    "scraped_at": "2024-06-15T10:00:00Z",
    "source_url": "https://www.screener.in/screens/dividend-yield/",
    "pe_ratio": 12.0,
    "market_cap_cr": 50000.0,
    "roce_pct": 18.0,
    "roe_pct": 22.0,
    "sales_growth_pct": 8.0,
}


def _make_envelope(records: list[dict]) -> dict:
    return {
        "meta": {
            "scraped_at": "2024-06-15T10:00:00Z",
            "source_url": "https://www.screener.in/screens/dividend-yield/",
            "collector_id": "c_test",
            "record_count": len(records),
        },
        "records": records,
    }


def _write_envelope(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(_make_envelope(records)), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: load_snapshots
# ---------------------------------------------------------------------------


class TestLoadSnapshots:
    def test_loads_records_from_existing_files(self, tmp_path: Path) -> None:
        latest_path = tmp_path / "latest.json"
        previous_path = tmp_path / "previous.json"
        _write_envelope(latest_path, [_BASE_RECORD])
        _write_envelope(previous_path, [_BASE_RECORD])

        engine = DiffEngine()
        latest, previous = engine.load_snapshots(str(latest_path), str(previous_path))

        assert len(latest) == 1
        assert len(previous) == 1

    def test_missing_previous_returns_empty_list(self, tmp_path: Path) -> None:
        latest_path = tmp_path / "latest.json"
        _write_envelope(latest_path, [_BASE_RECORD])
        missing_previous = str(tmp_path / "does_not_exist.json")

        engine = DiffEngine()
        latest, previous = engine.load_snapshots(str(latest_path), missing_previous)

        assert len(latest) == 1
        assert previous == []


# ---------------------------------------------------------------------------
# Tests: diff — ENTERED
# ---------------------------------------------------------------------------


class TestDiffEntered:
    def test_new_ticker_classified_as_entered(self) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[])
        assert len(result.entered) == 1
        assert result.entered[0].ticker == "ALPHA"
        assert result.entered[0].status == "ENTERED"

    def test_first_run_flag_set_when_no_previous(self) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[])
        assert result.is_first_run is True

    def test_ticker_in_latest_not_in_previous_entered(self) -> None:
        beta = {**_BASE_RECORD, "ticker": "BETA", "company_name": "Beta Corp"}
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD, beta], previous=[_BASE_RECORD])
        assert len(result.entered) == 1
        assert result.entered[0].ticker == "BETA"


# ---------------------------------------------------------------------------
# Tests: diff — EXITED
# ---------------------------------------------------------------------------


class TestDiffExited:
    def test_ticker_absent_from_latest_classified_as_exited(self) -> None:
        beta = {**_BASE_RECORD, "ticker": "BETA", "company_name": "Beta Corp"}
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[_BASE_RECORD, beta])
        assert len(result.exited) == 1
        assert result.exited[0].ticker == "BETA"
        assert result.exited[0].status == "EXITED"

    def test_empty_latest_all_exited(self) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[], previous=[_BASE_RECORD])
        assert len(result.exited) == 1
        assert result.entered == []
        assert result.changed == []
        assert result.unchanged == []


# ---------------------------------------------------------------------------
# Tests: diff — CHANGED
# ---------------------------------------------------------------------------


class TestDiffChanged:
    def test_dividend_yield_change_above_threshold_classified_changed(self) -> None:
        updated = {**_BASE_RECORD, "dividend_yield_pct": 4.2}  # delta = 0.7 > 0.5
        engine = DiffEngine()
        result = engine.diff(latest=[updated], previous=[_BASE_RECORD])
        assert len(result.changed) == 1
        assert result.changed[0].ticker == "ALPHA"

    def test_cmp_change_above_5pct_classified_changed(self) -> None:
        updated = {**_BASE_RECORD, "cmp": 108.0}  # 8% change > 5%
        engine = DiffEngine()
        result = engine.diff(latest=[updated], previous=[_BASE_RECORD])
        assert len(result.changed) == 1

    def test_pe_ratio_change_above_2_classified_changed(self) -> None:
        updated = {**_BASE_RECORD, "pe_ratio": 14.5}  # delta = 2.5 > 2
        engine = DiffEngine()
        result = engine.diff(latest=[updated], previous=[_BASE_RECORD])
        assert len(result.changed) == 1

    def test_field_going_null_classified_changed(self) -> None:
        updated = {**_BASE_RECORD, "pe_ratio": None}
        engine = DiffEngine()
        result = engine.diff(latest=[updated], previous=[_BASE_RECORD])
        assert len(result.changed) == 1
        delta_fields = [d.field for d in result.changed[0].deltas]
        assert "pe_ratio" in delta_fields

    def test_changed_record_contains_deltas(self) -> None:
        updated = {**_BASE_RECORD, "dividend_yield_pct": 4.2}
        engine = DiffEngine()
        result = engine.diff(latest=[updated], previous=[_BASE_RECORD])
        deltas = result.changed[0].deltas
        assert any(d.field == "dividend_yield_pct" for d in deltas)
        delta = next(d for d in deltas if d.field == "dividend_yield_pct")
        assert delta.old_value == pytest.approx(3.5)
        assert delta.new_value == pytest.approx(4.2)


# ---------------------------------------------------------------------------
# Tests: diff — UNCHANGED
# ---------------------------------------------------------------------------


class TestDiffUnchanged:
    def test_identical_record_classified_unchanged(self) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[_BASE_RECORD])
        assert len(result.unchanged) == 1
        assert result.unchanged[0].ticker == "ALPHA"
        assert result.unchanged[0].status == "UNCHANGED"
        assert result.unchanged[0].deltas == []

    def test_small_dividend_yield_change_below_threshold_unchanged(self) -> None:
        updated = {**_BASE_RECORD, "dividend_yield_pct": 3.7}  # delta = 0.2 < 0.5
        engine = DiffEngine()
        result = engine.diff(latest=[updated], previous=[_BASE_RECORD])
        assert len(result.unchanged) == 1

    def test_small_cmp_change_below_5pct_unchanged(self) -> None:
        updated = {**_BASE_RECORD, "cmp": 103.0}  # 3% change < 5%
        engine = DiffEngine()
        result = engine.diff(latest=[updated], previous=[_BASE_RECORD])
        assert len(result.unchanged) == 1

    def test_is_first_run_false_when_previous_exists(self) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[_BASE_RECORD])
        assert result.is_first_run is False


# ---------------------------------------------------------------------------
# Tests: custom thresholds
# ---------------------------------------------------------------------------


class TestDiffCustomThresholds:
    def test_custom_dividend_yield_threshold(self) -> None:
        updated = {**_BASE_RECORD, "dividend_yield_pct": 3.6}  # delta = 0.1
        engine = DiffEngine()

        # With tight threshold (0.05) → CHANGED
        result_changed = engine.diff(
            latest=[updated],
            previous=[_BASE_RECORD],
            thresholds={"dividend_yield_pct": 0.05},
        )
        assert len(result_changed.changed) == 1

        # With wide threshold (1.0) → UNCHANGED
        result_unchanged = engine.diff(
            latest=[updated],
            previous=[_BASE_RECORD],
            thresholds={"dividend_yield_pct": 1.0},
        )
        assert len(result_unchanged.unchanged) == 1


# ---------------------------------------------------------------------------
# Tests: write_report
# ---------------------------------------------------------------------------


class TestWriteReport:
    def test_creates_report_file(self, tmp_path: Path) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[])
        path = engine.write_report(result, output_dir=str(tmp_path))
        assert Path(path).exists()

    def test_report_contains_run_header(self, tmp_path: Path) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[])
        path = engine.write_report(result, output_dir=str(tmp_path))
        content = Path(path).read_text(encoding="utf-8")
        assert "## Run at" in content

    def test_report_contains_entered_ticker(self, tmp_path: Path) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[])
        path = engine.write_report(result, output_dir=str(tmp_path))
        content = Path(path).read_text(encoding="utf-8")
        assert "ALPHA" in content

    def test_second_run_appends_separator(self, tmp_path: Path) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[])
        path = engine.write_report(result, output_dir=str(tmp_path))
        engine.write_report(result, output_dir=str(tmp_path))
        content = Path(path).read_text(encoding="utf-8")
        assert "---" in content

    def test_snapshot_date_from_record(self, tmp_path: Path) -> None:
        engine = DiffEngine()
        result = engine.diff(latest=[_BASE_RECORD], previous=[])
        path = engine.write_report(result, output_dir=str(tmp_path))
        assert "2024-06-15" in path
