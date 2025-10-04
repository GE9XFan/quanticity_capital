PYTHON ?= python3
PIP ?= pip3

.PHONY: install install-dev compile lint test run docker-build docker-up docker-down format ingest-run ingest-test ingest-replay

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements.txt pip-tools

compile:
	pip-compile requirements.in --output-file requirements.txt

lint:
	PYTHONPATH=src $(PYTHON) -m compileall src

test:
	PYTHONPATH=src $(PYTHON) -m pytest -q

run:
	PYTHONPATH=src uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload

ingest-run:
	PYTHONPATH=src $(PYTHON) -m ingestion

ingest-test:
	PYTHONPATH=src $(PYTHON) -m pytest -q tests/ingestion

ingest-replay:
	@echo "Replay harness not implemented yet"

docker-build:
	docker compose build

docker-up:
	docker compose up

docker-down:
	docker compose down
