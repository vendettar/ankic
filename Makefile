## Simple task runner for tests and quality checks

PY := uv run

.PHONY: help test type lint fmt fmt-check qa ci

help:
	@echo "make test        - run unit tests (pytest)"
	@echo "make type        - run mypy type checks"
	@echo "make lint        - run ruff lint"
	@echo "make fmt         - run black formatter"
	@echo "make fmt-check   - check formatting with black --check"
	@echo "make qa          - run tests + type + lint + fmt-check"
	@echo "make ci          - alias for qa"

test:
	ENABLE_AUDIO=true ANKI_AUDIO_DELAY=0 AUDIO_OFFLINE=true ANKIC_FAST=true $(PY) pytest -q

type:
	$(PY) mypy anki_connector --ignore-missing-imports

lint:
	$(PY) ruff check anki_connector

fmt:
	$(PY) black .

fmt-check:
	$(PY) black --check .

qa: test type lint fmt-check

ci: qa
