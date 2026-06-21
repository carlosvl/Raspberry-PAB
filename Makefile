.PHONY: help venv install install-dev run run-kiosk test lint format typecheck clean

PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
PYTHONPATH := src

help:
	@echo "Raspberry-PAB kiosk development targets"
	@echo ""
	@echo "  make venv          Create virtual environment"
	@echo "  make install       Install package (production deps)"
	@echo "  make install-dev   Install package + dev dependencies"
	@echo "  make run           Run the kiosk web server"
	@echo "  make run-kiosk     Run server (open http://127.0.0.1:8080 in browser)"
	@echo "  make test          Run tests with coverage"
	@echo "  make lint          Run ruff linter"
	@echo "  make format        Auto-format with ruff"
	@echo "  make typecheck     Run mypy"
	@echo "  make clean         Remove build artifacts and cache"

venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

install: venv
	$(BIN)/pip install .

install-dev: venv
	$(BIN)/pip install -e ".[dev]"

run:
	PYTHONPATH=$(PYTHONPATH) $(BIN)/raspberry-pab

run-kiosk: run

test:
	PYTHONPATH=$(PYTHONPATH) $(BIN)/pytest --cov=raspberry_pab --cov-report=term-missing

lint:
	$(BIN)/ruff check src tests

format:
	$(BIN)/ruff format src tests
	$(BIN)/ruff check --fix src tests

typecheck:
	$(BIN)/mypy

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
