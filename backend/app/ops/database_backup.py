from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from app.core.observability import configure_logging, log_event, redact

logger = logging.getLogger(__name__)
_ARTIFACT = re.compile(r"^urban_dev_(\d{8}_\d{6}_\d{6}Z)\.dump$")
_VALIDATION_PREFIX = "phase60_restore_validation_"


def backup_filename(now: datetime | None = None) -> str:
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    return f"urban_dev_{instant.strftime('%Y%m%d_%H%M%S_%fZ')}.dump"


def _connection(database_url: str) -> tuple[str, dict[str, str], str]:
    parsed = urlsplit(database_url)
    if parsed.scheme.split("+", 1)[0] not in {"postgres", "postgresql"} or not parsed.hostname:
        raise ValueError("DATABASE_URL must be a PostgreSQL URL")
    scheme = "postgresql"
    host = parsed.hostname
    if parsed.port:
        host += f":{parsed.port}"
    user = unquote(parsed.username or "")
    auth = user + "@" if user else ""
    clean = urlunsplit((scheme, auth + host, parsed.path, parsed.query, ""))
    env = os.environ.copy()
    if parsed.password is not None:
        env["PGPASSWORD"] = unquote(parsed.password)
    database = parsed.path.lstrip("/")
    if not database:
        raise ValueError("DATABASE_URL must include a database name")
    return clean, env, database


def create_backup(database_url: str, directory: Path, *, runner=subprocess.run,
                  now: datetime | None = None) -> Path:
    connection, env, _ = _connection(database_url)
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / backup_filename(now)
    partial = artifact.with_suffix(".dump.partial")
    try:
        result = runner(["pg_dump", "--format=custom", "--no-owner", "--no-acl",
                         "--file", str(partial), connection], env=env, check=False,
                        capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("pg_dump failed")
        if not partial.is_file() or partial.stat().st_size <= 0:
            raise RuntimeError("pg_dump produced an empty artifact")
        partial.replace(artifact)
        log_event(logger, logging.INFO, "database.backup.succeeded", artifact=str(artifact),
                  size_bytes=artifact.stat().st_size)
        return artifact
    except Exception as exc:
        partial.unlink(missing_ok=True)
        log_event(logger, logging.ERROR, "database.backup.failed",
                  error_category=exc.__class__.__name__, error=str(exc))
        raise


def latest_backup(directory: Path) -> Path:
    candidates = sorted(path for path in directory.glob("urban_dev_*.dump") if _ARTIFACT.fullmatch(path.name))
    if not candidates:
        raise FileNotFoundError("no timestamped backup artifact found")
    return candidates[-1]


def validate_restore(database_url: str, artifact: Path, *, runner=subprocess.run) -> str:
    connection, env, source_database = _connection(database_url)
    if not artifact.is_file() or artifact.stat().st_size <= 0:
        raise ValueError("backup artifact is missing or empty")
    validation_database = _VALIDATION_PREFIX + uuid.uuid4().hex
    maintenance = connection.rsplit("/", 1)[0] + "/postgres"
    created = False
    stage = "temporary_db_create"
    command = []
    result = None

    def execute(args):
        nonlocal command, result
        command = args
        result = None
        result = runner(args, env=env, check=False, capture_output=True, text=True)
        return result

    def safe(value):
        text = str(value or "")
        secrets = [env.get("PGPASSWORD", "")]
        secrets.extend(value for key, value in env.items()
                       if re.search(r"password|secret|token|credential|api_?key", key, re.I))
        for secret in sorted(set(secrets), key=len, reverse=True):
            if secret:
                text = text.replace(secret, "[REDACTED]")
        return redact(text)[:4000]

    def diagnostic():
        return dict(failure_stage=stage, command=[safe(arg) for arg in command],
                    returncode=getattr(result, "returncode", None),
                    stderr=safe(getattr(result, "stderr", "")),
                    stdout=safe(getattr(result, "stdout", "")))

    try:
        create = execute(["createdb", "--maintenance-db", maintenance, validation_database])
        if create.returncode != 0:
            raise RuntimeError("temporary validation database creation failed")
        created = True
        validation_url = connection.rsplit("/", 1)[0] + "/" + validation_database
        stage = "pg_restore"
        restored = execute(["pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
                            "--dbname", validation_url, str(artifact)])
        # pg_dump 17 emits this initial session setting even for a PG16 source.
        # Only this exact failure is eligible: exit-on-error stopped before DDL.
        if (restored.returncode != 0
                and 'unrecognized configuration parameter "transaction_timeout"' in restored.stderr
                and "Command was: SET transaction_timeout = 0;" in restored.stderr):
            log_event(logger, logging.WARNING, "database.restore_validation.compatibility_retry",
                      **diagnostic())
            with tempfile.TemporaryDirectory(prefix="phase60_restore_") as directory:
                raw = Path(directory) / "restore.sql"
                compatible = Path(directory) / "compatible.sql"
                stage = "pg_restore_sql"
                rendered = execute(["pg_restore", "--no-owner", "--no-acl", "--file", str(raw), str(artifact)])
                if rendered.returncode != 0:
                    raise RuntimeError("restore SQL generation failed")
                removed = False
                with raw.open("rb") as source, compatible.open("wb") as target:
                    for line in source:
                        if not removed and line.rstrip(b"\r\n") == b"SET transaction_timeout = 0;":
                            removed = True
                            continue
                        target.write(line)
                if not removed:
                    raise RuntimeError("expected initial transaction_timeout setting missing")
                stage = "restore_sql"
                restored = execute(["psql", "-X", "--set", "ON_ERROR_STOP=1",
                                    "--dbname", validation_url, "--file", str(compatible)])
        if restored.returncode != 0:
            raise RuntimeError("restore validation failed")
        stage = "validation_query"
        checked = execute(["psql", "-X", "--set", "ON_ERROR_STOP=1", "--dbname", validation_url,
                           "--tuples-only", "--no-align", "--command", "SELECT current_database();"])
        if checked.returncode != 0 or checked.stdout.strip() != validation_database:
            raise RuntimeError("restored database connection validation failed")
    except Exception as exc:
        log_event(logger, logging.ERROR, "database.restore_validation.failed",
                  artifact=str(artifact), error_category=exc.__class__.__name__, error=safe(exc),
                  **diagnostic())
        raise
    finally:
        if created:
            failed = sys.exc_info()[0] is not None
            stage = "cleanup"
            try:
                dropped = execute(["dropdb", "--maintenance-db", maintenance, "--if-exists", validation_database])
            except Exception as exc:
                log_event(logger, logging.CRITICAL, "database.restore_validation.cleanup_failed",
                          validation_database=validation_database, error=safe(exc), **diagnostic())
                if not failed:
                    raise
                dropped = None
            if dropped is not None and dropped.returncode != 0:
                log_event(logger, logging.CRITICAL, "database.restore_validation.cleanup_failed",
                          validation_database=validation_database, **diagnostic())
                if not failed:
                    raise RuntimeError("temporary validation database cleanup failed")
    log_event(logger, logging.INFO, "database.restore_validation.succeeded",
              artifact=str(artifact), validation_database=validation_database,
              source_database=source_database)
    return validation_database


def main(argv: list[str] | None = None) -> int:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    parser = argparse.ArgumentParser(description="PostgreSQL backup and isolated restore validation")
    parser.add_argument("operation", choices=("backup", "validate"))
    parser.add_argument("--directory", default=os.getenv("BACKUP_DIRECTORY", "/backups"))
    parser.add_argument("--artifact")
    args = parser.parse_args(argv)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        log_event(logger, logging.ERROR, "database.operation.failed", error_category="configuration_error",
                  error="DATABASE_URL is required")
        return 2
    try:
        directory = Path(args.directory)
        if args.operation == "backup":
            create_backup(database_url, directory)
        else:
            validate_restore(database_url, Path(args.artifact) if args.artifact else latest_backup(directory))
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
