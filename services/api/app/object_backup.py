"""Command-line object backup. Binary archive data is always streamed on stdio."""

import argparse
import sys

from app.object_archive import verify_archive
from app.s3_blobstore import configured_blobstore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("export", "verify", "check-empty", "restore")
    )
    args = parser.parse_args()
    try:
        if args.action == "verify":
            verify_archive(sys.stdin.buffer)
        else:
            store = configured_blobstore()
            if args.action == "export":
                store.export_archive(sys.stdout.buffer)
            elif args.action == "check-empty":
                store.ensure_empty()
            else:
                store.restore_archive(sys.stdin.buffer)
    except Exception:
        print(
            "Object backup operation failed; check the archive and local store configuration.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
