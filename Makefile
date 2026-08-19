VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: venv install test test-schema test-diff test-scraper test-health test-analyser scrape diff smoke selfheal crawl-check clean

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

test-health: install
	$(PYTHON) -m pytest tests/test_health_check.py -v

test-analyser: install
	$(PYTHON) -m pytest tests/test_page_analyser.py -v

## Live runs (requires .env with real secrets)

scrape:
	@set -a && source .env && set +a && $(PYTHON) src/run_scrape.py

diff:
	$(PYTHON) src/run_diff.py

smoke: scrape diff
	$(PYTHON) scripts/smoke_check.py

selfheal:
	@set -a && source .env && set +a && $(PYTHON) src/run_selfheal.py

crawl-check:
	@set -a && source .env && set +a && $(PYTHON) scripts/crawl_check.py

## Cleanup

clean:
	rm -rf $(VENV) __pycache__ src/__pycache__ tests/__pycache__ .pytest_cache
