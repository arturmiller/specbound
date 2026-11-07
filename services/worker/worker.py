"""Idle worker process; job execution will be introduced by a later task."""

import logging
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            status, body = 200, b'{"status":"ok","mode":"idle","processing":false}'
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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stop = threading.Event()

    def shutdown(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    server = ThreadingHTTPServer(("127.0.0.1", 8081), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Worker started; no job queue configured")
    stop.wait()
    server.shutdown()
    server.server_close()
    thread.join()
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
