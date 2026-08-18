"""Schema validation for scraped Screener.in records."""

import json
import os
from typing import Any

import jsonschema

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "schema.json")


class SchemaValidationError(Exception):
    """Raised when a record does not conform to the canonical schema."""


def _load_schema() -> dict:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_record(record: dict[str, Any]) -> None:
    """Validate a single scraped record against the canonical JSON Schema.

    Raises:
        SchemaValidationError: if the record fails validation, with a
            human-readable message naming the offending field.
    """
    schema = _load_schema()
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(record), key=lambda e: e.path)
    if errors:
        messages = "; ".join(
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        )
        raise SchemaValidationError(f"Record failed schema validation: {messages}")
