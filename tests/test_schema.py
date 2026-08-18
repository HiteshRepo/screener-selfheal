"""Tests for src/schema.py — validate_record() and sample.json conformance."""

import json
import os
import sys

import pytest

# Allow importing from src/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schema import SchemaValidationError, validate_record  # noqa: E402

_SAMPLE_JSON = os.path.join(os.path.dirname(__file__), "..", "data", "sample.json")


def _load_sample_records() -> list[dict]:
    with open(_SAMPLE_JSON, encoding="utf-8") as fh:
        envelope = json.load(fh)
    return envelope["records"]


# ---------------------------------------------------------------------------
# Fixtures
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


# ---------------------------------------------------------------------------
# Tests: data/sample.json records
# ---------------------------------------------------------------------------


class TestSampleJson:
    def test_sample_records_pass_validation(self) -> None:
        records = _load_sample_records()
        assert len(records) >= 3, "sample.json should have at least 3 records"
        for record in records:
            validate_record(record)  # must not raise

    def test_sample_records_have_required_fields(self) -> None:
        required = {
            "company_name",
            "ticker",
            "exchange",
            "cmp",
            "dividend_yield_pct",
            "scraped_at",
            "source_url",
        }
        for record in _load_sample_records():
            missing = required - record.keys()
            assert not missing, f"Record {record.get('ticker')} missing fields: {missing}"


# ---------------------------------------------------------------------------
# Tests: validate_record() happy paths
# ---------------------------------------------------------------------------


class TestValidateRecordValid:
    def test_minimal_required_fields_pass(self) -> None:
        validate_record(VALID_RECORD)  # must not raise

    def test_null_optional_fields_pass(self) -> None:
        record = {**VALID_RECORD, "pe_ratio": None, "market_cap_cr": None}
        validate_record(record)  # must not raise

    def test_all_optional_fields_present(self) -> None:
        record = {
            **VALID_RECORD,
            "pe_ratio": 12.5,
            "market_cap_cr": 50000.0,
            "roce_pct": 18.3,
            "roe_pct": 22.1,
            "sales_growth_pct": 8.7,
        }
        validate_record(record)  # must not raise


# ---------------------------------------------------------------------------
# Tests: validate_record() validation failures
# ---------------------------------------------------------------------------


class TestValidateRecordInvalid:
    def test_missing_ticker_raises(self) -> None:
        record = {k: v for k, v in VALID_RECORD.items() if k != "ticker"}
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_record(record)
        assert "ticker" in str(exc_info.value)

    def test_missing_dividend_yield_raises(self) -> None:
        record = {k: v for k, v in VALID_RECORD.items() if k != "dividend_yield_pct"}
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_record(record)
        assert "dividend_yield_pct" in str(exc_info.value)

    def test_missing_company_name_raises(self) -> None:
        record = {k: v for k, v in VALID_RECORD.items() if k != "company_name"}
        with pytest.raises(SchemaValidationError):
            validate_record(record)

    def test_missing_cmp_raises(self) -> None:
        record = {k: v for k, v in VALID_RECORD.items() if k != "cmp"}
        with pytest.raises(SchemaValidationError):
            validate_record(record)

    def test_wrong_type_for_cmp_raises(self) -> None:
        record = {**VALID_RECORD, "cmp": "not-a-number"}
        with pytest.raises(SchemaValidationError):
            validate_record(record)

    def test_error_message_names_field(self) -> None:
        record = {k: v for k, v in VALID_RECORD.items() if k != "ticker"}
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_record(record)
        assert "ticker" in str(exc_info.value).lower()
