PYTHON ?= python3.11
VENV   := .venv
BIN    := $(VENV)/bin

.PHONY: setup db test test-fast lint format run

setup:  ## create the venv, install dependencies and a local .env
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	@test -f .env || (cp .env.example .env && echo "Created .env - add your ANTHROPIC_API_KEY")

db:  ## start Postgres (docker compose) and wait until healthy
	docker compose up -d --wait

test: db  ## full test suite
	$(BIN)/pytest -q

test-fast: db  ## skip the YOLO inference tests
	$(BIN)/pytest -q -m "not yolo"

lint:  ## ruff lint + format check (same as CI)
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:  ## auto-fix lint issues and format
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

run: db  ## API server on http://localhost:8000 (docs at /docs)
	$(BIN)/uvicorn api.main:create_app --factory --reload
