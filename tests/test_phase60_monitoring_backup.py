from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.observability import StructuredJsonFormatter, redact
from app.main import app
from app.ops.database_backup import backup_filename, create_backup, validate_restore
from app.models import LawUpdateRunItem
from app.services.law_update_scheduler_service import _finish_failure
from app.services.live_law_change_persistence_service import _monitor_change
from app.services.operational_alert_service import emit_operational_alert


def _events(caplog, name):
    return [record for record in caplog.records if getattr(record, "event", None) == name]


def test_structured_formatter_and_all_required_secret_redaction():
    record = logging.LogRecord("phase60", logging.ERROR, __file__, 1, "failure", (), None)
    record.event = "test.secret"
    record.details = {
        "database_url": "postgresql+psycopg://user:fake-db-password@postgres:5432/db",
        "POSTGRES_PASSWORD": "fake-postgres-password",
        "Authorization": "Bearer fake-bearer-token",
        "api_key": "fake-api-key",
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "credential": "fake-credential",
    }
    output = StructuredJsonFormatter().format(record)
    payload = json.loads(output)
    assert payload["event"] == "test.secret" and payload["timestamp"] and payload["level"] == "ERROR"
    for secret in ("fake-db-password", "fake-postgres-password", "fake-bearer-token", "fake-api-key",
                   "fake-access-token", "fake-refresh-token", "fake-credential"):
        assert secret not in output
    assert "[REDACTED]" in output
    assert redact("Authorization: Bearer another-fake-token") == "Authorization:[REDACTED] [REDACTED]"


def test_normal_validation_4xx_5xx_and_unhandled_monitoring(caplog):
    if not any(getattr(route, "path", None) == "/phase60/expected" for route in app.routes):
        @app.get("/phase60/expected")
        def expected():
            raise HTTPException(status_code=409, detail="expected")

        @app.get("/phase60/validation/{number}")
        def validation(number: int):
            return {"number": number}

        @app.get("/phase60/server-error")
        def server_error():
            raise HTTPException(status_code=503, detail="unavailable")

        @app.get("/phase60/unhandled")
        def unhandled():
            raise RuntimeError("fake-password=must-not-leak")

    caplog.set_level(logging.INFO)
    client = TestClient(app, raise_server_exceptions=False)
    normal = client.get("/health", headers={"X-Request-ID": "phase60-normal"})
    validation = client.get("/phase60/validation/not-an-int")
    expected = client.get("/phase60/expected")
    server = client.get("/phase60/server-error")
    unhandled = client.get("/phase60/unhandled")
    assert normal.status_code == 200 and normal.headers["X-Request-ID"] == "phase60-normal"
    assert validation.status_code == 422 and expected.status_code == 409
    assert server.status_code == 503 and unhandled.status_code == 500
    assert _events(caplog, "http.request.completed")
    assert _events(caplog, "http.request.validation_error")
    assert _events(caplog, "http.request.expected_error")
    assert _events(caplog, "http.request.unhandled_exception")
    assert "must-not-leak" not in " ".join(record.getMessage() for record in caplog.records)


def test_request_correlation_is_concurrency_safe_and_rejects_unsafe_external_id():
    client = TestClient(app)
    request_ids = [f"parallel-{index}" for index in range(12)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        returned = list(pool.map(lambda value: client.get("/health", headers={"X-Request-ID": value}).headers["X-Request-ID"], request_ids))
    assert returned == request_ids and len(set(returned)) == len(returned)
    generated = client.get("/health", headers={"X-Request-ID": "bad id\r\nvalue"}).headers["X-Request-ID"]
    assert generated != "bad id\r\nvalue" and len(generated) == 32


def test_collection_amendment_and_alert_fallback_events(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    monkeypatch.delenv("OPERATIONAL_ALERT_DESTINATION", raising=False)
    emit_operational_alert("test.alert", severity="error", api_key="fake-api-key")
    result = SimpleNamespace(version_changed=True, content_changed=True, changed_articles=[{"article_no": "1"}],
                             event=SimpleNamespace(id=7), event_created=True)
    selection = SimpleNamespace(from_mst="100", to_mst="200")
    _monitor_change(result, "safe-law-id", selection)
    alerts = _events(caplog, "operational.alert")
    amendments = _events(caplog, "law.amendment.evaluated")
    assert alerts and getattr(alerts[0], "destination") == "structured_log"
    assert amendments and getattr(amendments[0], "changed_article_count") == 1
    assert "fake-api-key" not in " ".join(str(record.__dict__) for record in caplog.records)


def test_collection_failure_monitoring_includes_retry_and_safe_identifier(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    monkeypatch.delenv("OPERATIONAL_ALERT_DESTINATION", raising=False)
    class FakeSession:
        def commit(self):
            return None
    item = LawUpdateRunItem(run_id=11, registry_id=None, law_identifier="safe-law-id",
                            law_name="fixture law", status="running", retry_count=2,
                            started_at=datetime.now(UTC))
    _finish_failure(FakeSession(), item, "connection_timeout", "Authorization: Bearer fake-token")
    failures = _events(caplog, "law.collection.failed")
    assert failures and getattr(failures[0], "retry_count") == 2
    assert getattr(failures[0], "law_identifier") == "safe-law-id"
    assert "fake-token" not in str(failures[0].__dict__)


class Result:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = "fake failure detail"


def test_backup_success_timestamp_and_no_password_in_command(tmp_path):
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        Path(command[command.index("--file") + 1]).write_bytes(b"valid-fake-dump")
        return Result()
    artifact = create_backup("postgresql+psycopg://app:fake-db-password@postgres:5432/urban_dev", tmp_path,
                             runner=runner, now=datetime(2026, 8, 19, 1, 2, 3, 456789, tzinfo=UTC))
    assert artifact.name == "urban_dev_20260819_010203_456789Z.dump"
    assert artifact.stat().st_size > 0 and "fake-db-password" not in " ".join(calls[0][0])
    assert calls[0][1]["env"]["PGPASSWORD"] == "fake-db-password"


def test_backup_failure_is_non_success_and_removes_partial(tmp_path):
    def runner(command, **kwargs):
        Path(command[command.index("--file") + 1]).write_bytes(b"incomplete")
        return Result(1)
    try:
        create_backup("postgresql://app:fake@postgres/db", tmp_path, runner=runner)
        assert False, "failure must not be reported as success"
    except RuntimeError:
        pass
    assert not list(tmp_path.iterdir())


def test_restore_validation_uses_disposable_database_and_always_drops_it(tmp_path):
    artifact = tmp_path / backup_filename(datetime(2026, 8, 19, tzinfo=UTC))
    artifact.write_bytes(b"fake-dump")
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        result = Result()
        if command[0] == "psql":
            result.stdout = command[command.index("--dbname") + 1].rsplit("/", 1)[1] + "\n"
        return result
    validation_db = validate_restore("postgresql://app:fake@postgres:5432/application_db", artifact, runner=runner)
    assert validation_db.startswith("phase60_restore_validation_") and validation_db != "application_db"
    assert [call[0] for call in calls] == ["createdb", "pg_restore", "psql", "dropdb"]
    assert validation_db in calls[0] and validation_db in calls[-1]
    assert "application_db" not in calls[-1]


def test_restore_cleanup_failure_is_not_reported_as_success(tmp_path):
    artifact = tmp_path / backup_filename(datetime(2026, 8, 19, tzinfo=UTC))
    artifact.write_bytes(b"fake-dump")
    def runner(command, **kwargs):
        result = Result(1 if command[0] == "dropdb" else 0)
        if command[0] == "psql":
            result.stdout = command[command.index("--dbname") + 1].rsplit("/", 1)[1]
        return result
    try:
        validate_restore("postgresql://app:fake@postgres:5432/application_db", artifact, runner=runner)
        assert False, "cleanup failure must fail validation"
    except RuntimeError as exc:
        assert "cleanup failed" in str(exc)


def test_backup_artifacts_are_git_ignored_and_compose_operations_are_one_shot():
    ignore = Path(".gitignore").read_text(encoding="utf-8-sig")
    dev = Path("compose.dev.yml").read_text(encoding="utf-8-sig")
    prod = Path("compose.prod.yml").read_text(encoding="utf-8-sig")
    assert "backups/" in ignore
    for compose in (dev, prod):
        assert 'profiles: ["operations"]' in compose
        assert "app.ops.database_backup" in compose
        assert "down -v" not in compose


def test_pg17_dump_pg16_restore_compatibility_and_secret_diagnostics(tmp_path, caplog):
    artifact = tmp_path / backup_filename()
    artifact.write_bytes(b"fake-dump")
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        result = Result()
        if command[0] == "pg_restore" and "--dbname" in command:
            result.returncode = 1
            result.stderr = ('ERROR: unrecognized configuration parameter "transaction_timeout"\n'
                             'Command was: SET transaction_timeout = 0;\nprivate-password')
        elif command[0] == "pg_restore":
            Path(command[command.index("--file") + 1]).write_bytes(
                b"SET transaction_timeout = 0;\nCREATE TABLE example (id integer);\n")
        elif command[0] == "psql":
            target = command[command.index("--dbname") + 1]
            assert "application_db" not in target
            if "--file" in command:
                sql = Path(command[command.index("--file") + 1]).read_bytes()
                assert b"transaction_timeout" not in sql and b"CREATE TABLE" in sql
            else:
                result.stdout = target.rsplit("/", 1)[1]
        return result
    validate_restore("postgresql://app:private-password@postgres/application_db", artifact, runner=runner)
    assert [call[0] for call in calls] == ["createdb", "pg_restore", "pg_restore", "psql", "psql", "dropdb"]
    event = _events(caplog, "database.restore_validation.compatibility_retry")[0]
    assert event.failure_stage == "pg_restore" and event.returncode == 1
    assert "private-password" not in str(event.__dict__)


def test_unrelated_restore_failure_does_not_retry_or_hide_primary_error(tmp_path, caplog):
    artifact = tmp_path / backup_filename()
    artifact.write_bytes(b"fake-dump")
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        result = Result(0 if command[0] == "createdb" else 1)
        result.stderr = "permission denied private-password"
        return result
    import pytest
    with pytest.raises(RuntimeError, match="restore validation failed"):
        validate_restore("postgresql://app:private-password@postgres/application_db", artifact, runner=runner)
    assert [call[0] for call in calls] == ["createdb", "pg_restore", "dropdb"]
    failure = _events(caplog, "database.restore_validation.failed")[0]
    assert failure.failure_stage == "pg_restore" and failure.returncode == 1
    assert "private-password" not in str(failure.__dict__)
