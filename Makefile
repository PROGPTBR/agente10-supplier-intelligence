.PHONY: help up down logs build test test-backend test-frontend lint lint-backend lint-frontend fmt migrate install-hooks clean

help:
	@echo "Targets:"
	@echo "  up              start the full dev stack (postgres, redis, backend, frontend)"
	@echo "  down            stop and remove containers + volumes"
	@echo "  logs            tail logs of all services"
	@echo "  build           rebuild images"
	@echo "  test            run backend + frontend tests"
	@echo "  test-backend    run backend tests only"
	@echo "  test-frontend   run frontend tests only"
	@echo "  lint            run all linters"
	@echo "  fmt             apply formatters"
	@echo "  migrate         apply alembic migrations"
	@echo "  install-hooks   install pre-commit hooks"

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

test-backend:
	docker compose run --rm backend uv run pytest -q

test-frontend:
	cd frontend && pnpm test

test: test-backend test-frontend

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
