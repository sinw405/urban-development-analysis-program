from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import LawUpdateRun
from app.services.law_update_scheduler_service import BatchAlreadyRunning, run_law_update_batch, run_summary

JOB_ID = "phase44-law-update"
_scheduler: BackgroundScheduler | None = None


def start_law_update_scheduler(scheduler_factory=BackgroundScheduler) -> bool:
    global _scheduler
    settings = get_settings()
    if not settings.law_update_scheduler_enabled:
        return False
    if _scheduler is not None and _scheduler.running:
        return False
    scheduler = scheduler_factory(timezone="UTC")
    scheduler.add_job(_scheduled_run, "interval", hours=settings.law_update_scheduler_interval_hours,
        id=JOB_ID, replace_existing=True, max_instances=1, coalesce=True, next_run_time=datetime.now(UTC))
    scheduler.start()
    _scheduler = scheduler
    return True


def shutdown_law_update_scheduler(wait: bool = True) -> bool:
    global _scheduler
    if _scheduler is None:
        return False
    if _scheduler.running:
        _scheduler.shutdown(wait=wait)
    _scheduler = None
    return True


def scheduler_status() -> dict[str, Any]:
    settings = get_settings()
    job = None if _scheduler is None else _scheduler.get_job(JOB_ID)
    with SessionLocal() as db:
        last = db.scalar(select(LawUpdateRun).order_by(LawUpdateRun.id.desc()).limit(1))
        success = db.scalar(select(LawUpdateRun).where(LawUpdateRun.status == "completed").order_by(LawUpdateRun.id.desc()).limit(1))
    return {
        "enabled": settings.law_update_scheduler_enabled,
        "running": bool(_scheduler is not None and _scheduler.running),
        "last_run": None if last is None else run_summary(last),
        "last_success": None if success is None else run_summary(success),
        "next_run": None if job is None else job.next_run_time,
        "latest_status": None if last is None else last.status,
        "interval_hours": settings.law_update_scheduler_interval_hours,
        "secret_exposed": False,
    }


def _scheduled_run():
    try:
        run_law_update_batch("scheduled")
    except BatchAlreadyRunning:
        return