import unittest
from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient


class HealthEndpointTest(unittest.TestCase):
    def test_health_endpoint_returns_json(self) -> None:
        with TestClient(app) as client:
            response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_fails_closed_without_leaking_dependency_details(self):
        with TestClient(app) as client:
            with patch(
                "app.main.check_readiness",
                side_effect=RuntimeError("sensitive dependency detail"),
            ):
                response = client.get("/readyz")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("sensitive", response.text)
            with patch("app.main.check_readiness"):
                response = client.get("/readyz")
            self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
