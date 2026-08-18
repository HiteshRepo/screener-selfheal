"""Tests for src/health_check.py — health_check() and HealthReport."""

import os
import sys
from dataclasses import FrozenInstanceError

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SRC = os.path.join(_ROOT, "src")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from health_check import HealthReport, HealthStatus, health_check  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_RECORD = {
    "company_name": "Test Corp",
    "ticker": "TSTCORP",
    "exchange": "NSE",
    "cmp": 100.0,
    "dividend_yield_pct": 3.5,
    "scraped_at": "2024-06-15T10:00:00Z",
    "source_url": "https://www.screener.in/screens/dividend-yield/",
}

INVALID_RECORD = {"company_name": "Bad Corp"}  # missing required fields


def _make_envelope(records: list, record_count: int | None = None) -> dict:
    count = record_count if record_count is not None else len(records)
    return {"meta": {"record_count": count}, "records": records}


# ---------------------------------------------------------------------------
# Tests: HealthReport immutability
# ---------------------------------------------------------------------------


class TestHealthReportImmutable:
    def test_mutating_status_raises(self) -> None:
        report = HealthReport(status=HealthStatus.HEALTHY, reason="")
        with pytest.raises(FrozenInstanceError):
            report.status = HealthStatus.BROKEN  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: health_check() — BROKEN scenarios
# ---------------------------------------------------------------------------


class TestHealthCheckBroken:
    def test_empty_records_returns_broken(self) -> None:
        envelope = _make_envelope(records=[])
        report = health_check(envelope)
        assert report.status == HealthStatus.BROKEN
        assert "No records" in report.reason

    def test_count_mismatch_returns_broken(self) -> None:
        envelope = _make_envelope(records=[VALID_RECORD, VALID_RECORD], record_count=5)
        report = health_check(envelope)
        assert report.status == HealthStatus.BROKEN
        assert "mismatch" in report.reason.lower()

    def test_count_mismatch_reason_names_declared_and_actual(self) -> None:
        envelope = _make_envelope(records=[VALID_RECORD], record_count=3)
        report = health_check(envelope)
        assert "3" in report.reason
        assert "1" in report.reason

    def test_all_invalid_records_returns_broken(self) -> None:
        envelope = _make_envelope(records=[INVALID_RECORD, INVALID_RECORD])
        report = health_check(envelope)
        assert report.status == HealthStatus.BROKEN


# ---------------------------------------------------------------------------
# Tests: health_check() — DEGRADED scenario
# ---------------------------------------------------------------------------


class TestHealthCheckDegraded:
    def test_partial_failures_returns_degraded(self) -> None:
        envelope = _make_envelope(records=[VALID_RECORD, VALID_RECORD, INVALID_RECORD])
        report = health_check(envelope)
        assert report.status == HealthStatus.DEGRADED
        assert report.reason != ""

    def test_degraded_reason_mentions_failing_fraction(self) -> None:
        envelope = _make_envelope(records=[VALID_RECORD, INVALID_RECORD])
        report = health_check(envelope)
        # reason should mention how many out of how many failed
        assert "1" in report.reason
        assert "2" in report.reason


# ---------------------------------------------------------------------------
# Tests: health_check() — HEALTHY scenario
# ---------------------------------------------------------------------------


class TestHealthCheckHealthy:
    def test_all_valid_records_returns_healthy(self) -> None:
        envelope = _make_envelope(records=[VALID_RECORD, VALID_RECORD, VALID_RECORD])
        report = health_check(envelope)
        assert report.status == HealthStatus.HEALTHY

    def test_healthy_reason_is_empty(self) -> None:
        envelope = _make_envelope(records=[VALID_RECORD])
        report = health_check(envelope)
        assert report.reason == ""
