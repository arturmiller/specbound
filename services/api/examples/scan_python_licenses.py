"""Read-only operator preview; this does not create Specbound assessments."""

import argparse
import json
import sys

from app.git_source import GitSourceError
from app.github_source import configured_github_source
from app.python_license_scan import scan_python_repository


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repository", help="GitHub owner/repository in the configured App installation"
    )
    parser.add_argument("ref", help="Git branch, tag, or commit to resolve once")
    args = parser.parse_args(argv)
    try:
        source = configured_github_source(args.repository)
        try:
            result = scan_python_repository(source, args.ref)
        finally:
            source.close()
    except (GitSourceError, ValueError):
        print("GitHub repository or configured source is unavailable", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(package["status"] == "FAIL" for package in result["packages"]):
        return 1
    return 0 if result["coverage"] == "covered" else 2


if __name__ == "__main__":
    raise SystemExit(main())
