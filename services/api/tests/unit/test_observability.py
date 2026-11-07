"""Local metrics and request logs avoid credentials and report meaningful lag."""

import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.main import app
from app.metrics import render_metrics
from app.structured_logging import JsonFormatter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


class ObservabilityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.engine.begin() as db:
            db.execute(
                text(
                    "CREATE TABLE assessment_jobs (status VARCHAR(20), created_at DATETIME)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO assessment_jobs (status, created_at) VALUES (:status, :created)"
                ),
                [
                    {
                        "status": "pending",
                        "created": (self.now - timedelta(seconds=42)).replace(
                            tzinfo=None
                        ),
                    },
                    {"status": "running", "created": self.now.replace(tzinfo=None)},
                ],
            )

    def tearDown(self):
        self.engine.dispose()

    def test_aggregate_metrics_include_pending_job_lag(self):
        with self.engine.connect() as db:
            metrics = render_metrics(db, now=self.now)
        self.assertIn('specbound_jobs{status="pending"} 1', metrics)
        self.assertIn('specbound_jobs{status="running"} 1', metrics)
        self.assertIn("specbound_oldest_pending_job_seconds 42.000", metrics)

    def test_metrics_are_opt_in_and_request_logs_exclude_query_values(self):
        with (
            TestClient(app) as client,
            self.assertLogs("specbound.http", level="INFO") as captured,
        ):
            with patch.dict(os.environ, {"METRICS_ENABLED": "false"}):
                self.assertEqual(
                    client.get("/metrics?token=secret-example").status_code, 404
                )
            with (
                patch.dict(os.environ, {"METRICS_ENABLED": "true"}),
                patch("app.main.get_engine", return_value=self.engine),
            ):
                self.assertEqual(client.get("/metrics").status_code, 200)
        self.assertEqual(captured.records[0].path, "/metrics")
        self.assertNotIn("secret-example", JsonFormatter().format(captured.records[0]))
        formatted = json.loads(JsonFormatter().format(captured.records[0]))
        self.assertEqual((formatted["method"], formatted["status_code"]), ("GET", 404))
