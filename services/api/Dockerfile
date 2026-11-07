FROM python:3.12-slim
WORKDIR /app
COPY services/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/api/app ./app
COPY services/api/alembic.ini ./alembic.ini
COPY services/api/logging.json ./logging.json
COPY services/api/migrations ./migrations
COPY services/api/tests ./tests
COPY contracts ./contracts
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "logging.json", "--no-access-log"]
