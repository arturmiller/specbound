FROM python:3.12-slim AS python-base

FROM python-base AS dependencies
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv
COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv sync --locked --only-group runtime --python /usr/local/bin/python --no-cache

FROM python-base
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
COPY --from=dependencies /app/.venv /app/.venv
COPY services/api/app ./app
COPY services/api/alembic.ini ./alembic.ini
COPY services/api/logging.json ./logging.json
COPY services/api/migrations ./migrations
COPY services/api/tests ./tests
COPY contracts ./contracts
COPY policies/python-license ./policies/python-license
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "logging.json", "--no-access-log"]
