.PHONY: install check check-front lint typecheck test fmt seed run dev-front fixtures documents scenarios

install:
	uv sync
	cd frontend && npm install

check: lint typecheck test

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest -q

fmt:
	uv run ruff format .
	uv run ruff check --fix .

fixtures:
	uv run python scripts/generate_fixtures.py

documents:
	uv run python scripts/generate_documents.py

seed:
	uv run python scripts/seed.py

# Modo demonstração: atraso por caixa do grafo para visualizar o fluxo (DEMO_DELAY_MS=0 desliga).
DEMO_DELAY_MS ?= 500
DEMO_TOOL_DELAY_MS ?= 400

run: seed
	CLAIMS_DEMO__NODE_DELAY_MS=$(DEMO_DELAY_MS) CLAIMS_DEMO__TOOL_DELAY_MS=$(if $(filter 0,$(DEMO_DELAY_MS)),0,$(DEMO_TOOL_DELAY_MS)) \
		uv run uvicorn claims_agents.api.app:app --reload --port 8000

check-front:
	cd frontend && npm run build

dev-front:
	cd frontend && npm run dev

scenarios:
	uv run python scripts/run_scenarios.py --suite smoke
