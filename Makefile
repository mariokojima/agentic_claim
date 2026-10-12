.PHONY: install check lint typecheck test fmt seed run dev-front fixtures scenarios

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

seed:
	uv run python scripts/seed.py

run: seed
	uv run uvicorn claims_agents.api.app:app --reload --port 8000

dev-front:
	cd frontend && npm run dev

scenarios:
	uv run python scripts/run_scenarios.py --suite smoke
