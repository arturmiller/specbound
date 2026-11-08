"""A write response must not precede its database transaction outcome."""

import unittest
from unittest.mock import patch

from app.identity import get_current_principal
from app.main import app
from fastapi.testclient import TestClient


class Result:
    def mappings(self):
        return self

    def one(self):
        return {"id": "org-test", "name": "Test", "owner_principal_id": "user:test"}


class Connection:
    def execute(self, _statement):
        return Result()


class Transaction:
    def __init__(self, events, fail):
        self.events = events
        self.fail = fail

    def __enter__(self):
        return Connection()

    def __exit__(self, exc_type, _exc, _traceback):
        if exc_type:
            self.events.append("rollback")
        elif self.fail:
            self.events.append("commit-failed")
            raise RuntimeError("simulated commit failure")
        else:
            self.events.append("commit")


class Engine:
    def __init__(self, events, fail=False):
        self.events = events
        self.fail = fail

    def begin(self):
        return Transaction(self.events, self.fail)


class TraceResponse:
    def __init__(self, wrapped, events):
        self.wrapped = wrapped
        self.events = events

    async def __call__(self, scope, receive, send):
        async def trace(message):
            if message["type"] == "http.response.start":
                self.events.append(f"response:{message['status']}")
            await send(message)

        await self.wrapped(scope, receive, trace)


class TransactionResponseTest(unittest.TestCase):
    def run_request(self, fail=False):
        events = []
        original = app.dependency_overrides.copy()
        app.dependency_overrides[get_current_principal] = lambda: "user:test"
        try:
            with patch("app.database.get_engine", return_value=Engine(events, fail)):
                with TestClient(TraceResponse(app, events), raise_server_exceptions=False) as client:
                    response = client.post("/organizations", json={"name": "Test"})
        finally:
            app.dependency_overrides = original
        return response, events

    def test_success_is_sent_only_after_commit(self):
        response, events = self.run_request()
        self.assertEqual(response.status_code, 201)
        self.assertLess(events.index("commit"), events.index("response:201"), events)

    def test_commit_failure_cannot_return_success(self):
        response, events = self.run_request(fail=True)
        self.assertEqual(response.status_code, 500, events)
        self.assertNotIn("response:201", events)
