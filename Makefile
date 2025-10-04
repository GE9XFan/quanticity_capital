PYTHON ?= python3
PIP ?= pip3

.PHONY: install install-dev compile lint test run docker-build docker-up docker-down format

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

docker-build:
	docker compose build

docker-up:
	docker compose up

docker-down:
	docker compose down
