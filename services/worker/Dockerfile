FROM python:3.12-slim
WORKDIR /app
COPY services/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/api/app ./app
COPY services/worker/worker.py ./worker.py
COPY services/worker/collector_runner.py ./collector_runner.py
COPY services/worker/queue_worker.py ./queue_worker.py
COPY services/worker/public_license_worker.py ./public_license_worker.py
COPY contracts ./contracts
COPY policies/python-license ./policies/python-license
CMD ["python", "-u", "worker.py"]
