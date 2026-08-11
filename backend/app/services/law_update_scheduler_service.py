from __future__ import annotations

import hashlib
import logging
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Callable, Iterator

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.models import LawUpdateRegistry, LawUpdateRun, LawUpdateRunItem
from app.services.moleg_live_client import MolegLiveClient
from app.services.moleg_version_discovery_service import analyze_live_law_change

logger = logging.getLogger(__name__)

def _scheduler_client() -> MolegLiveClient:
    return MolegLiveClient(retry_count=0)
BATCH_LOCK_KEY = 0x50483434
RETRYABLE_CODES = {"connection_timeout", "dns_error", "connection_refused", "proxy_error", "http_error_status", "unknown_connection_error"}

class BatchAlreadyRunning(RuntimeError):
    pass


def _lock_key(value: str) -> int:
    raw = int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big", signed=False)
    return raw if raw < 2**63 else raw - 2**64


@contextmanager
def advisory_lock(key: int) -> Iterator[bool]:
    connection = engine.connect()
    acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}))
    try:
        yield acquired
    finally:
        if acquired:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        connection.close()


def run_law_update_batch(
    trigger_type: str = "manual",
    *,
    session_factory=SessionLocal,
    client_factory: Callable[[], MolegLiveClient] = _scheduler_client,
    analyze_fn: Callable[..., Any] = analyze_live_law_change,
    lock_factory: Callable[[int], Any] = advisory_lock,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> LawUpdateRun:
    if trigger_type not in {"manual", "scheduled"}:
        raise ValueError("invalid trigger_type")
    with lock_factory(BATCH_LOCK_KEY) as acquired:
        if not acquired:
            raise BatchAlreadyRunning("law update batch is already running")
        started = datetime.now(UTC)
        with session_factory() as db:
            targets = list(db.scalars(select(LawUpdateRegistry).where(LawUpdateRegistry.enabled.is_(True)).order_by(LawUpdateRegistry.priority.desc(), LawUpdateRegistry.id)).all())
            target_data = [(row.id, row.law_identifier, row.law_name) for row in targets]
            run = LawUpdateRun(trigger_type=trigger_type, status="running", started_at=started, target_count=len(target_data))
            db.add(run); db.commit(); db.refresh(run); run_id = run.id
        for registry_id, law_identifier, law_name in target_data:
            _process_law(run_id, registry_id, law_identifier, law_name, session_factory, client_factory, analyze_fn, lock_factory, sleep_fn)
        with session_factory() as db:
            run = db.get(LawUpdateRun, run_id)
            items = list(db.scalars(select(LawUpdateRunItem).where(LawUpdateRunItem.run_id == run_id)).all())
            run.success_count = sum(item.status in {"no_change", "changed"} for item in items)
            run.no_change_count = sum(item.status == "no_change" for item in items)
            run.change_count = sum(item.status == "changed" for item in items)
            run.failed_count = sum(item.status not in {"no_change", "changed"} for item in items)
            run.created_event_count = sum(item.event_created for item in items)
            run.finished_at = datetime.now(UTC)
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            run.status = "completed" if run.failed_count == 0 else "failed" if run.success_count == 0 else "partial"
            db.commit(); db.refresh(run)
            logger.info("law update run completed run_id=%s status=%s elapsed_ms=%s", run.id, run.status, run.duration_ms)
            return run


def _process_law(run_id, registry_id, law_identifier, law_name, session_factory, client_factory, analyze_fn, lock_factory, sleep_fn):
    started = datetime.now(UTC)
    with lock_factory(_lock_key(f"law:{law_identifier}")) as acquired:
        with session_factory() as db:
            item = LawUpdateRunItem(run_id=run_id, registry_id=registry_id, law_identifier=law_identifier, law_name=law_name, status="running", started_at=started)
            db.add(item); db.commit(); db.refresh(item)
            if not acquired:
                return _finish_failure(db, item, "concurrent_law_run", "law already running")
            settings = get_settings()
            retries = settings.law_update_scheduler_retry_count
            backoff = settings.law_update_scheduler_retry_backoff_seconds
            result = None
            for attempt in range(retries + 1):
                item.retry_count = attempt
                try:
                    result = analyze_fn(db=db, client=client_factory(), law_name=law_name, ensure_versions=True, persist_event=True, dry_run=False)
                except Exception as exc:
                    if attempt < retries and _retryable_text(exc.__class__.__name__):
                        sleep_fn(backoff * (2**attempt)); continue
                    return _finish_failure(db, item, exc.__class__.__name__, exc.__class__.__name__)
                if result.status == "ok":
                    break
                errors = list(getattr(result, "errors", []))
                if attempt < retries and any(_retryable_text(error) for error in errors):
                    sleep_fn(backoff * (2**attempt)); continue
                return _finish_failure(db, item, errors[0] if errors else result.status, result.status)
            selection = result.selection
            phase = result.phase43
            item.status = "changed" if phase.content_changed else "no_change"
            item.from_mst = selection.from_mst
            item.to_mst = selection.to_mst
            item.version_changed = phase.version_changed
            item.content_changed = phase.content_changed
            item.event_id = None if phase.event is None else phase.event.id
            item.event_created = phase.event_created
            _finish_item(item)
            registry = db.get(LawUpdateRegistry, registry_id)
            registry.last_checked_at = item.finished_at
            registry.last_success_at = item.finished_at
            registry.last_detected_mst = item.to_mst
            db.commit()
            logger.info("law update item completed run_id=%s law=%s status=%s retry=%s event_id=%s", run_id, law_name, item.status, item.retry_count, item.event_id)


def _finish_failure(db: Session, item: LawUpdateRunItem, code: str, message: str):
    registry = db.get(LawUpdateRegistry, item.registry_id) if item.registry_id is not None else None
    if registry is not None:
        registry.last_checked_at = datetime.now(UTC)
    item.status = "failed"
    item.error_code = _sanitize(code, 100)
    item.sanitized_error = _sanitize(message, 1000)
    _finish_item(item); db.commit()
    logger.warning("law update item failed run_id=%s law=%s code=%s", item.run_id, item.law_name, item.error_code)


def _finish_item(item: LawUpdateRunItem):
    item.finished_at = datetime.now(UTC)
    item.duration_ms = int((item.finished_at - item.started_at).total_seconds() * 1000)


def _retryable_text(value: str) -> bool:
    text_value = str(value).lower()
    return any(code in text_value for code in RETRYABLE_CODES) or "timeout" in text_value or "connecterror" in text_value


def _sanitize(value: Any, limit: int) -> str:
    text_value = str(value)
    for marker in ("OC=", "serviceKey=", "MOLEG_API_KEY="):
        if marker in text_value:
            text_value = text_value.split(marker, 1)[0] + marker + "[REDACTED]"
    return text_value[:limit]


def run_summary(run: LawUpdateRun) -> dict[str, Any]:
    return {column.name: getattr(run, column.name) for column in LawUpdateRun.__table__.columns}


def item_summary(item: LawUpdateRunItem) -> dict[str, Any]:
    return {column.name: getattr(item, column.name) for column in LawUpdateRunItem.__table__.columns}


def recent_runs(db: Session, limit: int = 20) -> list[LawUpdateRun]:
    return list(db.scalars(select(LawUpdateRun).order_by(LawUpdateRun.id.desc()).limit(max(1, min(limit, 100)))).all())