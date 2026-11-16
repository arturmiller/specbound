"""Bounded worker subprocess for one credential-free public license scan."""

import json
import sys

from app.git_source import SourceNotFound, SourceUnavailable
from app.public_github_source import PublicGitHubRateLimit, PublicGitHubSource
from app.python_license_scan import scan_python_repository


def main():
    if len(sys.argv) != 3:
        return 2
    try:
        source = PublicGitHubSource(sys.argv[1])
        try:
            result = scan_python_repository(source, sys.argv[2])
        finally:
            source.close()
        response = {"status": "ok", "result": result}
    except PublicGitHubRateLimit:
        response = {"status": "error", "errorCode": "rate-limited"}
    except SourceNotFound:
        response = {"status": "error", "errorCode": "source-not-found"}
    except (SourceUnavailable, ValueError):
        response = {"status": "error", "errorCode": "source-unavailable"}
    except Exception:
        response = {"status": "error", "errorCode": "scanner-failed"}
    print(json.dumps(response, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
