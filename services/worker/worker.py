"""Idle worker process; job execution will be introduced by a later task."""

import logging
import signal
import threading


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stop = threading.Event()

    def shutdown(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    logging.info("Worker started; no job queue configured")
    stop.wait()
    logging.info("Worker stopped")


if __name__ == "__main__":
    main()
