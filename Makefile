PYTHON ?= python3.11
VENV   := .venv
BIN    := $(VENV)/bin

.PHONY: setup db test test-fast lint format run web

setup:  ## create the venv, install dependencies and a local .env
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	cd web && npm install
	@test -f .env || (cp .env.example .env && echo "Created .env - add your ANTHROPIC_API_KEY")

db:  ## start Postgres (docker compose) and wait until healthy
	docker compose up -d --wait

test: db  ## full test suite
	$(BIN)/pytest -q
	cd web && npm test

test-fast: db  ## skip the YOLO inference tests
	$(BIN)/pytest -q -m "not yolo"

lint:  ## ruff lint + format check, web lint (same as CI)
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	cd web && npm run lint

format:  ## auto-fix lint issues and format
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

run: db  ## API server on http://localhost:8000 (docs at /docs)
	$(BIN)/uvicorn api.main:create_app --factory --reload

web:  ## dashboard on http://localhost:5173 (run `make run` in another terminal)
	cd web && npm run dev
