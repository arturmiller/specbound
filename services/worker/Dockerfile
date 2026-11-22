FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv
COPY services/worker/pyproject.toml services/worker/uv.lock ./
RUN uv sync --locked --only-group runtime --python /usr/local/bin/python --no-cache
ENV PATH="/app/.venv/bin:$PATH"
COPY services/api/app ./app
COPY services/worker/worker.py ./worker.py
COPY services/worker/collector_runner.py ./collector_runner.py
COPY services/worker/queue_worker.py ./queue_worker.py
COPY services/worker/public_license_worker.py ./public_license_worker.py
COPY services/worker/pr_license_worker.py ./pr_license_worker.py
COPY contracts ./contracts
COPY policies/python-license ./policies/python-license
CMD ["python", "-u", "worker.py"]
