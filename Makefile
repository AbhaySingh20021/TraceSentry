.PHONY: install test lint run

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

run:
	uvicorn tracesentry.main:app --reload
