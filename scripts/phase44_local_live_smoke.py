from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path: sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv
from sqlalchemy import select
from app.core.config import PROJECT_ROOT, get_settings
from app.core.database import SessionLocal
from app.models import LawUpdateRegistry, LawUpdateRunItem
from app.services.law_update_scheduler_service import BatchAlreadyRunning, run_law_update_batch
FIELDS = ["environment","scheduler_enabled","manual_run_started","run_id","target_count","success_count","no_change_count","change_count","failed_count","created_event_count","law_name","from_mst","to_mst","version_changed","content_changed","event_id","retry_count","run_status","duration","secret_exposed","FINAL RESULT"]

def main(argv=None):
    parser=argparse.ArgumentParser(description="Run one Phase 44 local live scheduler smoke batch.")
    parser.add_argument("--law-name", required=True)
    parser.add_argument("--law-identifier")
    parser.add_argument("--priority", type=int, default=0)
    args=parser.parse_args(argv)
    load_dotenv(PROJECT_ROOT / ".env", override=False); get_settings.cache_clear(); settings=get_settings()
    report={key:None for key in FIELDS}; report.update(environment="local_live",scheduler_enabled=settings.law_update_scheduler_enabled,manual_run_started=False,secret_exposed=False)
    if not settings.moleg_api_configured: return _fail(report,"credential")
    identifier=args.law_identifier or " ".join(args.law_name.casefold().split())
    try:
        with SessionLocal() as db:
            registry=db.scalar(select(LawUpdateRegistry).where(LawUpdateRegistry.law_identifier==identifier))
            if registry is None:
                registry=LawUpdateRegistry(law_identifier=identifier,law_name=args.law_name,enabled=True,priority=args.priority); db.add(registry)
            else:
                registry.law_name=args.law_name; registry.enabled=True; registry.priority=args.priority
            db.commit()
        report["manual_run_started"]=True
        run=run_law_update_batch("manual")
        with SessionLocal() as db:
            item=db.scalar(select(LawUpdateRunItem).where(LawUpdateRunItem.run_id==run.id,LawUpdateRunItem.law_identifier==identifier))
        report.update(run_id=run.id,target_count=run.target_count,success_count=run.success_count,no_change_count=run.no_change_count,change_count=run.change_count,failed_count=run.failed_count,created_event_count=run.created_event_count,law_name=None if item is None else item.law_name,from_mst=None if item is None else item.from_mst,to_mst=None if item is None else item.to_mst,version_changed=None if item is None else item.version_changed,content_changed=None if item is None else item.content_changed,event_id=None if item is None else item.event_id,retry_count=None if item is None else item.retry_count,run_status=run.status,duration=run.duration_ms)
        report["FINAL RESULT"]="PASS" if run.status=="completed" and item is not None else "FAIL: batch"
    except BatchAlreadyRunning: return _fail(report,"concurrency")
    except Exception: return _fail(report,"unknown")
    print(_render(report)); return 0 if report["FINAL RESULT"]=="PASS" else 1

def _fail(report,category):
    report["FINAL RESULT"]=f"FAIL: {category}"; print(_render(report)); return 1

def _render(report):
    return "\n".join(["PHASE 44 LOCAL LIVE SMOKE",""]+[f"{i}. {key}: {report.get(key)}" for i,key in enumerate(FIELDS,1)])
if __name__=="__main__": raise SystemExit(main())