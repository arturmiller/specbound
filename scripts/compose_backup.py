"""Back up or restore an explicitly selected, quiescent local Compose project."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNK = 1024 * 1024


class BackupError(RuntimeError):
    """A backup or restore precondition failed."""


def compose_command(project):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project):
        raise BackupError(
            "Project name must contain lowercase letters, digits, hyphens or underscores"
        )
    raw = os.environ.get("SPECBOUND_COMPOSE_COMMAND")
    command = json.loads(raw) if raw else ["docker", "compose"]
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(value, str) or not value for value in command)
    ):
        raise BackupError("Invalid Compose command")
    compose_file = os.environ.get("SPECBOUND_COMPOSE_FILE", str(ROOT / "compose.yaml"))
    return [*command, "-p", project, "-f", compose_file]


def run(command, *, stdin=None, stdout=subprocess.PIPE, description):
    try:
        return subprocess.run(
            command, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE, check=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BackupError(f"{description} failed") from exc


def require_quiescent(compose):
    for service in ("api", "web", "worker"):
        state = run(
            [*compose, "ps", "-q", "--status", "running", service],
            description="Inspecting Compose services",
        ).stdout
        if state.strip():
            raise BackupError("Stop the API, web and worker before backup or restore")
    for service in ("db", "minio"):
        state = run(
            [*compose, "ps", "-q", "--status", "running", service],
            description="Inspecting Compose services",
        ).stdout
        if not state.strip():
            raise BackupError(
                "Start the target database and MinIO before backup or restore"
            )


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK):
            value.update(chunk)
    return value.hexdigest()


def object_command(compose, action):
    return [
        *compose,
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "api",
        "python",
        "-m",
        "app.object_backup",
        action,
    ]


def backup(project, destination):
    compose = compose_command(project)
    require_quiescent(compose)
    destination.mkdir(exist_ok=False)
    database = destination / "database.dump"
    objects = destination / "objects.zip"
    with database.open("xb") as output:
        run(
            [
                *compose,
                "exec",
                "-T",
                "db",
                "pg_dump",
                "-U",
                "specbound",
                "-d",
                "specbound",
                "-Fc",
            ],
            stdout=output,
            description="Database backup",
        )
    with objects.open("xb") as output:
        run(
            object_command(compose, "export"),
            stdout=output,
            description="Object backup",
        )
    manifest = {
        "format": "specbound-compose-backup",
        "version": 1,
        "database": {"file": database.name, "sha256": digest(database)},
        "objects": {"file": objects.name, "sha256": digest(objects)},
    }
    with (destination / "manifest.json").open("x", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2)
        output.write("\n")


def checked_backup(source):
    manifest_path = source / "manifest.json"
    database, objects = source / "database.dump", source / "objects.zip"
    if any(
        not path.is_file() or path.is_symlink()
        for path in (manifest_path, database, objects)
    ):
        raise BackupError("Backup files are missing or are symbolic links")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            set(manifest) != {"format", "version", "database", "objects"}
            or manifest["format"] != "specbound-compose-backup"
            or type(manifest["version"]) is not int
            or manifest["version"] != 1
        ):
            raise ValueError("invalid manifest")
        for label, path in (("database", database), ("objects", objects)):
            item = manifest[label]
            if (
                not isinstance(item, dict)
                or set(item) != {"file", "sha256"}
                or item["file"] != path.name
                or item["sha256"] != digest(path)
            ):
                raise ValueError("checksum mismatch")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BackupError("Backup manifest or checksums are invalid") from exc
    return database, objects


def restore(project, source):
    compose = compose_command(project)
    require_quiescent(compose)
    database, objects = checked_backup(source)
    empty_sql = (
        "SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n "
        "ON n.oid=c.relnamespace WHERE n.nspname='public') + "
        "(SELECT count(*) FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid=p.pronamespace WHERE n.nspname='public') + "
        "(SELECT count(*) FROM pg_type t JOIN pg_namespace n "
        "ON n.oid=t.typnamespace WHERE n.nspname='public')"
    )
    count = run(
        [
            *compose,
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "specbound",
            "-d",
            "specbound",
            "-Atc",
            empty_sql,
        ],
        description="Checking the destination database",
    ).stdout.strip()
    if count != b"0":
        raise BackupError("Destination database is not empty")
    with objects.open("rb") as input_stream:
        run(
            object_command(compose, "verify"),
            stdin=input_stream,
            stdout=subprocess.DEVNULL,
            description="Object archive verification",
        )
    run(
        object_command(compose, "check-empty"),
        stdout=subprocess.DEVNULL,
        description="Checking the destination bucket",
    )
    with database.open("rb") as input_stream:
        run(
            [
                *compose,
                "exec",
                "-T",
                "db",
                "pg_restore",
                "-U",
                "specbound",
                "-d",
                "specbound",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
            ],
            stdin=input_stream,
            stdout=subprocess.DEVNULL,
            description="Database restore",
        )
    with objects.open("rb") as input_stream:
        try:
            run(
                object_command(compose, "restore"),
                stdin=input_stream,
                stdout=subprocess.DEVNULL,
                description="Object restore",
            )
        except BackupError as exc:
            raise BackupError(
                "Object restore failed after database restore; use a new empty target before retrying"
            ) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "restore"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--path", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.action == "backup":
            backup(args.project, args.path)
        else:
            restore(args.project, args.path)
    except (BackupError, OSError, ValueError) as exc:
        print(f"Operation failed: {exc}", file=sys.stderr)
        return 1
    print(f"{args.action.capitalize()} completed for Compose project {args.project}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
