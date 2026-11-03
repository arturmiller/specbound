FROM python:3.12-slim
WORKDIR /app
COPY services/worker/worker.py ./worker.py
COPY contracts ./contracts
CMD ["python", "-u", "worker.py"]
