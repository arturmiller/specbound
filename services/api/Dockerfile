FROM python:3.12-slim AS python-base

FROM python-base AS postgres-base
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/*

FROM postgres-base AS dependencies
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y gcc libc6-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv
COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv sync --locked --only-group runtime --only-group postgres-system \
    --no-binary-package psycopg-c --python /usr/local/bin/python --no-cache

FROM postgres-base
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PSYCOPG_IMPL=c
COPY --from=dependencies /app/.venv /app/.venv
RUN python -c 'from importlib.util import find_spec; from psycopg import pq; assert pq.__impl__ == "c" and find_spec("psycopg_binary") is None'
COPY services/api/app ./app
COPY services/api/alembic.ini ./alembic.ini
COPY services/api/logging.json ./logging.json
COPY services/api/migrations ./migrations
COPY services/api/tests ./tests
COPY contracts ./contracts
COPY policies/python-license ./policies/python-license
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "logging.json", "--no-access-log"]
