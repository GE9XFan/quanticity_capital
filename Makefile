.PHONY: install fmt lint typecheck test run

install:
	UV_CACHE_DIR=.uv-cache UV_PYTHON=python3.11 uv sync

fmt:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run mypy src

test:
	uv run pytest

run:
	uv run python3.11 src/main.py
