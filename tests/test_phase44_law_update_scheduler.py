from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models import LawUpdateRegistry, LawUpdateRun, LawUpdateRunItem
from app.services import law_update_scheduler_runtime as runtime
from app.services.law_update_scheduler_service import BatchAlreadyRunning, run_law_update_batch
from scripts.phase44_local_live_smoke import FIELDS, _render

@contextmanager
def allow_lock(_): yield True
@contextmanager
def deny_lock(_): yield False

def cleanup():
    with SessionLocal() as db:
        db.execute(delete(LawUpdateRunItem)); db.execute(delete(LawUpdateRun)); db.execute(delete(LawUpdateRegistry)); db.commit()

def add_laws(*names):
    with SessionLocal() as db:
        for i,name in enumerate(names): db.add(LawUpdateRegistry(law_identifier=f"L{i}",law_name=name,enabled=True,priority=len(names)-i))
        db.commit()

def result(changed=False, status="ok", errors=None, event_created=False):
    selection=SimpleNamespace(from_mst="1",to_mst="2")
    phase=SimpleNamespace(content_changed=changed,version_changed=True,event=None,event_created=event_created)
    return SimpleNamespace(status=status,errors=errors or [],selection=selection,phase43=phase)

@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cleanup(); monkeypatch.setenv("LAW_UPDATE_SCHEDULER_ENABLED","false"); monkeypatch.setenv("LAW_UPDATE_SCHEDULER_RETRY_COUNT","1"); monkeypatch.setenv("LAW_UPDATE_SCHEDULER_RETRY_BACKOFF_SECONDS","0"); get_settings.cache_clear(); runtime.shutdown_law_update_scheduler(False)
    yield
    runtime.shutdown_law_update_scheduler(False); cleanup(); get_settings.cache_clear()

def test_config_defaults_disabled_interval_and_invalid(monkeypatch):
    assert get_settings().law_update_scheduler_enabled is False
    assert get_settings().law_update_scheduler_interval_hours == 24
    monkeypatch.setenv("LAW_UPDATE_SCHEDULER_INTERVAL_HOURS","0"); get_settings.cache_clear()
    with pytest.raises(ValueError): _=get_settings().law_update_scheduler_interval_hours

def test_registered_laws_success_no_change_change_and_counts():
    add_laws("A","B")
    run=run_law_update_batch(analyze_fn=lambda **kw: result(changed=kw["law_name"]=="B", event_created=kw["law_name"]=="B"),lock_factory=allow_lock,sleep_fn=lambda _:None)
    assert (run.target_count,run.success_count,run.no_change_count,run.change_count,run.failed_count,run.created_event_count)==(2,2,1,1,0,1)
    with SessionLocal() as db: assert len(list(db.scalars(select(LawUpdateRunItem)).all()))==2

def test_failure_isolated_and_nonretryable_not_retried():
    add_laws("bad","good"); calls=[]
    def analyze(**kw):
        calls.append(kw["law_name"])
        return result(status="source_error",errors=["api_error_response"]) if kw["law_name"]=="bad" else result()
    run=run_law_update_batch(analyze_fn=analyze,lock_factory=allow_lock,sleep_fn=lambda _:None)
    assert run.status=="partial" and run.success_count==1 and run.failed_count==1
    assert calls.count("bad")==1 and calls.count("good")==1

def test_retryable_timeout_retries_once_then_succeeds():
    add_laws("A"); calls=[]
    def analyze(**_):
        calls.append(1); return result(status="source_error",errors=["connection_timeout"]) if len(calls)==1 else result()
    run=run_law_update_batch(analyze_fn=analyze,lock_factory=allow_lock,sleep_fn=lambda _:None)
    assert run.success_count==1 and len(calls)==2
    with SessionLocal() as db: assert db.scalar(select(LawUpdateRunItem)).retry_count==1

def test_retry_limit_stops():
    add_laws("A"); calls=[]
    def analyze(**_): calls.append(1); return result(status="source_error",errors=["connection_timeout"])
    run=run_law_update_batch(analyze_fn=analyze,lock_factory=allow_lock,sleep_fn=lambda _:None)
    assert run.failed_count==1 and len(calls)==2

def test_batch_concurrency_lock_blocks():
    with pytest.raises(BatchAlreadyRunning): run_law_update_batch(lock_factory=deny_lock)

def test_same_law_lock_blocks_item_but_batch_completes():
    add_laws("A"); states=iter([True,False])
    @contextmanager
    def locks(_): yield next(states)
    run=run_law_update_batch(lock_factory=locks)
    assert run.failed_count==1
    with SessionLocal() as db: assert db.scalar(select(LawUpdateRunItem)).error_code=="concurrent_law_run"

class FakeJob:
    next_run_time="next"
class FakeScheduler:
    def __init__(self,**kw): self.running=False; self.jobs=[]
    def add_job(self,*args,**kwargs): self.jobs.append((args,kwargs))
    def start(self): self.running=True
    def shutdown(self,wait=True): self.running=False
    def get_job(self,_): return FakeJob()

def test_scheduler_disabled_import_does_not_start():
    assert runtime._scheduler is None
    assert runtime.start_law_update_scheduler(FakeScheduler) is False

def test_scheduler_enabled_registers_once_interval_and_shutdown(monkeypatch):
    monkeypatch.setenv("LAW_UPDATE_SCHEDULER_ENABLED","true"); monkeypatch.setenv("LAW_UPDATE_SCHEDULER_INTERVAL_HOURS","3"); get_settings.cache_clear()
    assert runtime.start_law_update_scheduler(FakeScheduler) is True
    assert runtime.start_law_update_scheduler(FakeScheduler) is False
    assert runtime._scheduler.jobs[0][1]["hours"]==3 and runtime._scheduler.jobs[0][1]["max_instances"]==1
    assert runtime.shutdown_law_update_scheduler() is True and runtime._scheduler is None

def test_scheduler_status_api_and_recent_runs(monkeypatch):
    add_laws("A"); run=run_law_update_batch(analyze_fn=lambda **_:result(),lock_factory=allow_lock)
    client=TestClient(app)
    status=client.get("/api/law-updates/scheduler/status")
    recent=client.get("/api/law-updates/runs")
    detail=client.get(f"/api/law-updates/runs/{run.id}")
    assert status.status_code==200 and status.json()["enabled"] is False
    assert recent.status_code==200 and recent.json()["count"]==1
    assert detail.status_code==200 and len(detail.json()["items"])==1

def test_manual_run_api_uses_batch_service(monkeypatch):
    fake=SimpleNamespace(**{c.name:None for c in LawUpdateRun.__table__.columns}); fake.id=9; fake.status="completed"
    monkeypatch.setattr("app.api.law_updates.run_law_update_batch",lambda trigger: fake)
    response=TestClient(app).post("/api/law-updates/scheduler/run")
    assert response.status_code==200 and response.json()["run"]["id"]==9

def test_secret_masking_and_smoke_schema():
    rendered=_render({**{key:None for key in FIELDS},"FINAL RESULT":"PASS"})
    assert len(FIELDS)==21 and "FINAL RESULT: PASS" in rendered
    assert "MOLEG_API_KEY" not in rendered and "OC=" not in rendered