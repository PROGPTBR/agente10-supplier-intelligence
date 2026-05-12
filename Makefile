.PHONY: help up down logs build test test-backend test-backend-integration test-backend-voyage test-frontend test-integration lint lint-backend lint-frontend fmt migrate load-cnae bootstrap-data install-hooks clean

help:
	@echo "Targets:"
	@echo "  up                          start the full dev stack (postgres, redis, backend, frontend)"
	@echo "  down                        stop and remove containers + volumes"
	@echo "  logs                        tail logs of all services"
	@echo "  build                       rebuild images"
	@echo "  test                        run backend + frontend tests (excludes integration)"
	@echo "  test-backend                run backend unit tests"
	@echo "  test-backend-integration    run backend integration tests (requires postgres)"
	@echo "  test-backend-voyage         run CNAE golden tests (requires VOYAGE_API_KEY)"
	@echo "  test-frontend               run frontend tests only"
	@echo "  test-integration            run all integration tests"
	@echo "  lint                        run all linters"
	@echo "  fmt                         apply formatters"
	@echo "  migrate                     apply alembic migrations"
	@echo "  load-cnae                   populate cnae_taxonomy from bundled JSON"
	@echo "  bootstrap-data              migrate + load-cnae"
	@echo "  install-hooks               install pre-commit hooks"

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

build:
	docker compose build

migrate:
	docker compose run --rm backend uv run alembic upgrade head

load-cnae:
	docker compose run --rm backend uv run python scripts/load_cnae_taxonomy.py

bootstrap-data: migrate load-cnae

test-backend-voyage:
	docker compose up -d postgres
	docker compose run --rm \
		-e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 \
		backend uv run pytest -q -m "voyage and integration"

test-backend:
	docker compose run --rm backend uv run pytest -q -m "not integration"

test-backend-integration:
	docker compose up -d postgres
	docker compose run --rm -e INTEGRATION_DATABASE_URL=postgresql+asyncpg://agente10_app:agente10_dev@postgres:5432/agente10 backend uv run pytest -q -m integration

test-frontend:
	cd frontend && pnpm test

test: test-backend test-frontend

test-integration: test-backend-integration

lint-backend:
	docker compose run --rm backend uv run ruff check src tests
	docker compose run --rm backend uv run black --check src tests

lint-frontend:
	cd frontend && pnpm lint

lint: lint-backend lint-frontend

fmt:
	docker compose run --rm backend uv run ruff check --fix src tests
	docker compose run --rm backend uv run black src tests
	cd frontend && pnpm format

install-hooks:
	pre-commit install

clean:
	docker compose down -v
	docker image prune -f
