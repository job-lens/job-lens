"""Back up the Compose database or verify a trusted dump in a disposable database."""

import argparse
import hashlib
import os
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def compose(command: str, *args: str, **kwargs):
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "sh", "-c", command, "sh", *args],
        cwd=ROOT,
        check=True,
        timeout=600,
        **kwargs,
    )


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup(path: Path) -> None:
    sidecar = Path(str(path) + ".sha256")
    if path.exists() or sidecar.exists():
        raise FileExistsError("Refusing to overwrite a backup or checksum")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            compose(
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
                "--format=custom --no-owner --no-acl",
                stdout=stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
        with path.open("rb") as stream:
            if stream.read(5) != b"PGDMP":
                raise ValueError("pg_dump did not produce a custom archive")
        with sidecar.open("x", encoding="ascii") as stream:
            stream.write(checksum(path) + "\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def verify(path: Path) -> str:
    expected = Path(str(path) + ".sha256").read_text(encoding="ascii").strip()
    if expected != checksum(path):
        raise ValueError("Backup checksum mismatch")
    # No caller-provided restore target: production and existing databases are never replaced.
    target = f"job_lens_restore_{uuid4().hex}_test"
    compose('exec createdb -U "$POSTGRES_USER" -- "$1"', target)
    try:
        with path.open("rb") as stream:
            compose(
                'exec pg_restore -U "$POSTGRES_USER" -d "$1" '
                "--exit-on-error --no-owner --no-privileges",
                target,
                stdin=stream,
            )
        result = compose(
            'exec psql -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1 -At '
            '-c "SELECT version_num FROM alembic_version" '
            '-c "SELECT count(*) FROM jobs"',
            target,
            stdout=subprocess.PIPE,
            text=True,
        )
        rows = result.stdout.strip().splitlines()
        if len(rows) != 2 or not rows[0] or not rows[1].isdigit():
            raise ValueError("Restored database is missing migration or job data")
        return f"Restore verification passed: revision={rows[0]}, jobs={rows[1]}"
    finally:
        compose('exec dropdb -U "$POSTGRES_USER" -- "$1"', target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["backup", "verify"])
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "backup":
            backup(args.file)
            print(f"Backup and SHA-256 written: {args.file}")
        else:
            print(verify(args.file))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Database backup/verification failed: {exc}\n")


if __name__ == "__main__":
    main()
