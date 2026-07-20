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
from sqlalchemy import select

from app.core.config import PROJECT_ROOT, get_settings
from app.core.database import SessionLocal
from app.models import LawChangeImpactEvent, ProcedureArticleReviewEvent
from app.services.law_version_impact_service import LawVersionImpactService, list_law_change_impact_events
from app.services.moleg_live_client import MolegLiveClient
from app.services.moleg_version_discovery_service import analyze_live_law_change
from app.services.procedure_article_review_service import candidate_detail, confirm_candidate, list_review_candidates, reject_candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze stored MOLEG law version changes against procedure article mappings.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["analyze", "apply"]:
        p = sub.add_parser(name)
        p.add_argument("--law-name", required=True)
        p.add_argument("--from-mst")
        p.add_argument("--to-mst")
        p.add_argument("--auto-discover", action="store_true", help="Discover the latest/current and previous MOLEG versions when MSTs are omitted.")
        p.add_argument("--base-url")
        p.add_argument("--timeout-seconds", type=float)
        p.add_argument("--trust-env", choices=["true", "false"], default=None)
        p.add_argument("--force-rollback", action="store_true")
    list_p = sub.add_parser("list")
    list_p.add_argument("--status")
    show_p = sub.add_parser("show")
    show_p.add_argument("--event-id", type=int, required=True)
    preview_p = sub.add_parser("preview")
    preview_p.add_argument("--event-id", type=int, required=True)
    candidates_p = sub.add_parser("list-candidates")
    candidates_p.add_argument("--status")
    audit_p = sub.add_parser("audit-history")
    audit_p.add_argument("--candidate-id", type=int, required=True)
    for name in ["confirm", "reject"]:
        p = sub.add_parser(name)
        p.add_argument("--candidate-id", type=int, required=True)
        p.add_argument("--reviewer", required=True)
        p.add_argument("--note", required=True)
        p.add_argument("--force-rollback", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    get_settings.cache_clear()
    db = SessionLocal()
    try:
        if args.command in {"analyze", "apply"}:
            if args.from_mst and args.to_mst and args.from_mst == args.to_mst:
                print(json.dumps({"status": "invalid_version_pair", "errors": ["same_mst_not_comparable"], "secret_exposed": False}, ensure_ascii=False, indent=2))
                return 1
            if args.from_mst and args.to_mst and not args.auto_discover:
                result = LawVersionImpactService(db).analyze(
                    law_name=args.law_name,
                    from_mst=args.from_mst,
                    to_mst=args.to_mst,
                    dry_run=args.command != "apply",
                    force_rollback=args.force_rollback,
                )
                print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
                return 0 if result.status == "ok" else 1
            trust_env = None if args.trust_env is None else args.trust_env == "true"
            result = analyze_live_law_change(
                db=db,
                client=MolegLiveClient(base_url=args.base_url, timeout_seconds=args.timeout_seconds, trust_env=trust_env),
                law_name=args.law_name,
                from_mst=args.from_mst,
                to_mst=args.to_mst,
                dry_run=args.command != "apply",
                force_rollback=args.force_rollback,
            )
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
            return 0 if result.status == "ok" else 1
        if args.command == "list":
            items = [_event_summary(event) for event in list_law_change_impact_events(db, status=args.status)]
            print(json.dumps({"items": items, "count": len(items), "secret_exposed": False, "raw_payload_stored": False}, ensure_ascii=False, indent=2, default=str))
            return 0
        if args.command == "show":
            event = db.get(LawChangeImpactEvent, args.event_id)
            if event is None:
                print(json.dumps({"status": "not_found", "event_id": args.event_id}, ensure_ascii=False))
                return 1
            print(json.dumps({column.name: getattr(event, column.name) for column in LawChangeImpactEvent.__table__.columns}, ensure_ascii=False, indent=2, default=str))
            return 0
        if args.command == "preview":
            event = db.get(LawChangeImpactEvent, args.event_id)
            if event is None:
                print(json.dumps({"status": "not_found", "event_id": args.event_id}, ensure_ascii=False))
                return 1
            payload = {"event": _event_summary(event), "candidate": None, "audit_history": []}
            if event.candidate_id is not None:
                payload["candidate"] = candidate_detail(db, event.candidate_id, include_article_text=True)
                payload["audit_history"] = _audit_history(db, event.candidate_id)
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            return 0
        if args.command == "list-candidates":
            items = list_review_candidates(db, status=args.status)
            print(json.dumps({"items": items, "count": len(items), "secret_exposed": False, "raw_payload_stored": False}, ensure_ascii=False, indent=2, default=str))
            return 0
        if args.command == "audit-history":
            print(json.dumps({"candidate_id": args.candidate_id, "items": _audit_history(db, args.candidate_id)}, ensure_ascii=False, indent=2, default=str))
            return 0
        if args.command == "confirm":
            result = confirm_candidate(db, args.candidate_id, args.reviewer, args.note, force_rollback=args.force_rollback)
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
            return 0 if result.status == "ok" else 1
        if args.command == "reject":
            result = reject_candidate(db, args.candidate_id, args.reviewer, args.note, force_rollback=args.force_rollback)
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
            return 0 if result.status == "ok" else 1
        return 1
    finally:
        db.close()


def _event_summary(event: LawChangeImpactEvent) -> dict[str, object]:
    return {
        "event_id": event.id,
        "law_name": event.law_name,
        "law_id": event.law_id,
        "from_mst": event.from_mst,
        "to_mst": event.to_mst,
        "from_effective_date": event.from_effective_date,
        "to_effective_date": event.to_effective_date,
        "article_no": event.article_no,
        "article_title": event.article_title,
        "change_type": event.change_type,
        "candidate_id": event.candidate_id,
        "procedure_code": event.affected_procedure_code,
        "procedure_name": event.affected_procedure_name,
        "impact_level": event.impact_level,
        "review_status": event.derived_review_status,
        "mapping_status": event.mapping_status,
        "detected_at": event.detected_at,
        "official_url_status": event.official_url_status,
    }


def _audit_history(db, candidate_id: int) -> list[dict[str, object]]:
    rows = db.scalars(
        select(ProcedureArticleReviewEvent)
        .where(ProcedureArticleReviewEvent.candidate_id == candidate_id)
        .order_by(ProcedureArticleReviewEvent.reviewed_at.asc(), ProcedureArticleReviewEvent.id.asc())
    ).all()
    return [
        {
            "event_id": row.id,
            "candidate_id": row.candidate_id,
            "previous_status": row.previous_status,
            "new_status": row.new_status,
            "reviewer": row.reviewer,
            "review_note": row.review_note,
            "reviewed_at": row.reviewed_at,
            "reviewed_mst": row.reviewed_mst,
            "reviewed_effective_date": row.reviewed_effective_date,
            "source": row.source,
        }
        for row in rows
    ]


if __name__ == "__main__":
    raise SystemExit(main())
