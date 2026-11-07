"""Idle worker process; job execution will be introduced by a later task."""

import json
import logging
import os
import signal
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.structured_logging import JsonFormatter

logger = logging.getLogger(__name__)


def publish_loop(stop):
    from app.database import get_engine
    from app.github_source import configured_github_source
    from app.pr_comment_delivery import publish_once

    organization = os.environ.get("GITHUB_ORGANIZATION_ID", "")
    portal = os.environ.get("PORTAL_PUBLIC_URL", "")
    if not organization or not portal:
        logger.warning(
            "Comment publishing is missing organization or portal configuration"
        )
        return
    while not stop.is_set():
        try:
            worked = publish_once(
                get_engine(),
                organization,
                configured_github_source,
                portal,
                clock=lambda: datetime.now(timezone.utc),
            )
        except Exception:
            logger.warning("Comment publishing unavailable")
            worked = False
        if not worked:
            stop.wait(5)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            publisher = getattr(self.server, "publisher", None)
            mode = "comment_publisher" if publisher and publisher.is_alive() else "idle"
            status, body = (
                200,
                json.dumps(
                    {"status": "ok", "mode": mode, "processing": False},
                    separators=(",", ":"),
                ).encode(),
            )
        elif self.path == "/readyz":
            status, body = 503, b'{"status":"not_ready","reason":"no_handler"}'
        else:
            status, body = 404, b'{"status":"not_found"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        pass


def main() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    stop = threading.Event()

    def shutdown(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    server = ThreadingHTTPServer(("127.0.0.1", 8081), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    publisher = None
    if os.environ.get("GITHUB_COMMENT_PUBLISHING", "").lower() == "true":
        publisher = threading.Thread(target=publish_loop, args=(stop,), daemon=True)
        server.publisher = publisher
        publisher.start()
    logger.info("Worker started; no job queue configured")
    stop.wait()
    server.shutdown()
    server.server_close()
    thread.join()
    if publisher:
        publisher.join()
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
