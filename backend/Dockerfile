FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Railway builds from the repo root (where .git is), so all paths are
# prefixed with `backend/`. Local docker-compose uses `context: ./backend`
# which would break these — but local prod compose is no longer used (moved
# to Railway). Local dev still uses the same paths via docker-compose.yml
# which sets `context: ./backend` — that needs adjustment if dev compose
# is revived later.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project

COPY backend/src ./src
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "uvicorn", "agente10.main:app", "--host", "0.0.0.0", "--port", "8000"]
