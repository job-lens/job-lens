.PHONY: bootstrap api web migrate worker test check generate up down
bootstrap:
	uv sync --locked
	pnpm install --frozen-lockfile
api:
	uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
web:
	pnpm dev
migrate:
	uv run alembic -c apps/api/alembic.ini upgrade head
worker:
	uv run python -m app.worker
test:
	uv run pytest
	pnpm test
check:
	uv run ruff check .
	uv run mypy
	uv run python tools/check_architecture.py
	uv run python tools/check_contract.py
	uv run python tools/generate_architecture.py --check
	uv run python tools/export_openapi.py --check
	pnpm check:boundaries
	pnpm lint
	pnpm typecheck
generate:
	pnpm generate:api
	uv run python tools/generate_architecture.py
	uv run python tools/export_openapi.py
up:
	docker compose up -d --build --wait --wait-timeout 180
down:
	docker compose down
