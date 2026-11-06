"""Test-only server: an in-process identity override, never enabled by the application."""

import os

import uvicorn
from app.identity import get_current_principal
from app.main import app


def main():
    test_url = os.environ.get("SPECBOUND_E2E_DATABASE_URL")
    if not test_url:
        raise RuntimeError("SPECBOUND_E2E_DATABASE_URL must point to a disposable test database")
    os.environ["DATABASE_URL"] = test_url
    app.dependency_overrides[get_current_principal] = lambda: "user:e2e"
    uvicorn.run(app, host="127.0.0.1", port=18762, log_level="warning")


if __name__ == "__main__":
    main()
