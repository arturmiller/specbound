import unittest

from app.main import app
from fastapi.testclient import TestClient


class HealthEndpointTest(unittest.TestCase):
    def test_health_endpoint_returns_json(self) -> None:
        with TestClient(app) as client:
            response = client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_ci_failure_probe(self) -> None:
        self.fail('Intentional temporary failure to verify pull request checks')


if __name__ == '__main__':
    unittest.main()
