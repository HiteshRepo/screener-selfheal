VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: venv install test test-schema test-diff test-scraper scrape diff smoke clean

## Setup

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -q -r requirements.txt pytest

## Tests

test: install
	$(PYTHON) -m pytest tests/ -v

test-schema: install
	$(PYTHON) -m pytest tests/test_schema.py -v

test-diff: install
	$(PYTHON) -m pytest tests/test_diff_engine.py -v

test-scraper: install
	$(PYTHON) -m pytest tests/test_scraper_client.py -v

## Live runs (requires .env with real secrets)

scrape:
	@set -a && source .env && set +a && $(PYTHON) src/run_scrape.py

diff:
	$(PYTHON) src/run_diff.py

smoke: scrape diff
	@$(PYTHON) - <<'EOF'
import json, sys
sys.path.insert(0, 'src')
from schema import validate_record
with open('data/latest.json', encoding='utf-8') as fh:
    envelope = json.load(fh)
records = envelope.get('records', [])
meta = envelope.get('meta', {})
assert meta.get('record_count') == len(records), \
    f"meta.record_count {meta['record_count']} != {len(records)}"
for r in records:
    validate_record(r)
print(f"OK — {len(records)} record(s) validated.")
EOF

## Cleanup

clean:
	rm -rf $(VENV) __pycache__ src/__pycache__ tests/__pycache__ .pytest_cache
