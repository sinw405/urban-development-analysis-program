from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
from sqlalchemy import func, select

from app.core.config import PROJECT_ROOT, get_settings
from app.core.database import SessionLocal
from app.models import ProcedureOfficialArticleCandidate
from app.services.law_version_impact_service import LawVersionImpactService
from app.services.moleg_live_client import MolegLiveClient
from app.services.moleg_version_discovery_service import discover_law_versions, ingest_law_versions
from app.services.moleg_version_diff_service import diff_moleg_versions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 41 live MOLEG law change discovery, ingest, diff, and impact dry-run.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["discover", "run"]:
        p = sub.add_parser(name)
        p.add_argument("--law-name", default="도시개발법")
        p.add_argument("--max-versions", type=int, default=6)
        p.add_argument("--base-url")
        p.add_argument("--timeout-seconds", type=float)
        p.add_argument("--trust-env", choices=["true", "false"], default=None)
        if name == "run":
            p.add_argument("--apply-ingest", action="store_true", help="Persist official live versions before diffing. Required for DB-backed diff.")
            p.add_argument("--apply-impact", action="store_true", help="Persist impact events. Default is impact dry-run.")
            p.add_argument("--force-rollback", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    get_settings.cache_clear()
    trust_env = None if args.trust_env is None else args.trust_env == "true"
    client = MolegLiveClient(base_url=args.base_url, timeout_seconds=args.timeout_seconds, trust_env=trust_env)
    discovery = discover_law_versions(client=client, law_name=args.law_name, max_versions=max(2, args.max_versions))
    if args.command == "discover":
        print(json.dumps(discovery.to_dict(), ensure_ascii=False, indent=2, default=str))
        return 0 if discovery.status == "ok" else 1

    payload: dict[str, object] = {"discovery": discovery.to_dict()}
    if discovery.selected_pair is None:
        payload["status"] = "different_mst_pair_not_found"
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 1
    previous, current = discovery.selected_pair
    selected = [previous, current]
    db = SessionLocal()
    try:
        ingest = ingest_law_versions(db=db, client=client, descriptors=selected, dry_run=not args.apply_ingest, force_rollback=args.force_rollback)
        payload["ingest"] = ingest.to_dict()
        if ingest.status not in {"ready", "completed"}:
            payload["status"] = ingest.status
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            return 1
        if not args.apply_ingest:
            payload["status"] = "ready_without_db_diff"
            payload["message"] = "Run again with --apply-ingest to persist official live versions and compute DB-backed diff."
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            return 0
        diff = diff_moleg_versions(db, args.law_name, previous.mst, current.mst)
        payload["diff"] = diff.to_dict()
        impact = LawVersionImpactService(db).analyze(args.law_name, previous.mst, current.mst, dry_run=not args.apply_impact, force_rollback=args.force_rollback)
        payload["impact"] = impact.to_dict()
        payload["candidate_summary"] = _candidate_summary(db, current.law_id)
        payload["status"] = "ok" if diff.status == "ok" and impact.status == "ok" else "partial"
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0 if payload["status"] == "ok" else 1
    finally:
        db.close()


def _candidate_summary(db, law_id: str | None) -> dict[str, object]:
    statement = select(ProcedureOfficialArticleCandidate)
    if law_id:
        statement = statement.where(ProcedureOfficialArticleCandidate.law_id == law_id)
    rows = list(db.scalars(statement).all())
    confidence: dict[str, int] = {}
    procedures: dict[str, int] = {}
    for row in rows:
        confidence[row.confidence_level or "unknown"] = confidence.get(row.confidence_level or "unknown", 0) + 1
        procedures[row.procedure_code] = procedures.get(row.procedure_code, 0) + 1
    return {
        "candidate_count": len(rows),
        "confirmed": sum(1 for row in rows if row.is_confirmed),
        "unconfirmed": sum(1 for row in rows if not row.is_confirmed and row.confirmed_source != "manual_review_rejected"),
        "rejected": sum(1 for row in rows if row.confirmed_source == "manual_review_rejected"),
        "confidence_counts": confidence,
        "procedure_counts": procedures,
        "secret_exposed": False,
        "raw_payload_stored": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
