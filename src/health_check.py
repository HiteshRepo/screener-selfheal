"""Health classification for downloaded scrape envelopes."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.schema import SchemaValidationError, validate_record


class HealthStatus(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BROKEN = "BROKEN"


@dataclass(frozen=True)
class HealthReport:
    status: HealthStatus
    reason: str


def health_check(envelope: dict[str, Any]) -> HealthReport:
    """Classify a scrape envelope and return a HealthReport.

    Checks (in order):
    1. Empty records list → BROKEN
    2. record_count mismatch → BROKEN
    3. All records fail validation → BROKEN
    4. Partial validation failures → DEGRADED
    5. All records valid → HEALTHY
    """
    records: list[dict] = envelope.get("records", [])
    meta: dict = envelope.get("meta", {})
    declared_count: int = meta.get("record_count", len(records))

    if not records:
        return HealthReport(status=HealthStatus.BROKEN, reason="No records returned")

    if declared_count != len(records):
        return HealthReport(
            status=HealthStatus.BROKEN,
            reason=(
                f"record_count mismatch: meta declares {declared_count} "
                f"but {len(records)} records present"
            ),
        )

    failures: list[str] = []
    for i, record in enumerate(records):
        try:
            validate_record(record)
        except SchemaValidationError as exc:
            failures.append(f"record[{i}]: {exc}")

    if not failures:
        return HealthReport(status=HealthStatus.HEALTHY, reason="")

    if len(failures) == len(records):
        reason = "All records failed validation: " + "; ".join(failures)
        return HealthReport(status=HealthStatus.BROKEN, reason=reason)

    reason = f"{len(failures)}/{len(records)} records failed validation: " + "; ".join(failures)
    return HealthReport(status=HealthStatus.DEGRADED, reason=reason)
