"""Test-only API process with real token validation and a disposable database."""

import os

import uvicorn
from app.main import app


def main():
    test_url = os.environ.get("SPECBOUND_E2E_DATABASE_URL")
    if not test_url:
        raise RuntimeError(
            "SPECBOUND_E2E_DATABASE_URL must point to a disposable test database"
        )
    os.environ["DATABASE_URL"] = test_url
    uvicorn.run(app, host="127.0.0.1", port=18765, log_level="warning")


if __name__ == "__main__":
    main()
