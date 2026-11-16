"""The idle worker reports liveness without claiming it can process jobs."""

import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker import HealthHandler, ThreadingHTTPServer  # noqa: E402


class WorkerHealthTest(unittest.TestCase):
    def test_public_license_preview_does_not_claim_assessment_readiness(self):
        class Worker:
            def is_alive(self):
                return True

        server = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
        server.license_worker = Worker()
        server.license_processing = threading.Event()
        server.license_processing.set()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/healthz", timeout=2) as response:
                self.assertEqual(json.load(response), {"status": "ok", "mode": "public_license_preview", "processing": True})
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/readyz", timeout=2)
            self.assertEqual(error.exception.code, 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_idle_worker_is_alive_but_not_ready_to_process(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/healthz", timeout=2) as response:
                self.assertEqual(
                    json.load(response),
                    {"status": "ok", "mode": "idle", "processing": False},
                )
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/readyz", timeout=2)
            self.assertEqual(error.exception.code, 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_comment_publisher_does_not_claim_assessment_readiness(self):
        class Publisher:
            def is_alive(self):
                return True

        server = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
        server.publishers = [Publisher()]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/healthz", timeout=2) as response:
                self.assertEqual(
                    json.load(response),
                    {
                        "status": "ok",
                        "mode": "github_publisher",
                        "processing": False,
                    },
                )
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/readyz", timeout=2)
            self.assertEqual(error.exception.code, 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
