from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.models import LawChangeImpactEvent
from app.services.law_version_impact_service import LawVersionImpactService, list_law_change_impact_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze stored MOLEG law version changes against procedure article mappings.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["analyze", "apply"]:
        p = sub.add_parser(name)
        p.add_argument("--law-name", required=True)
        p.add_argument("--from-mst", required=True)
        p.add_argument("--to-mst", required=True)
        p.add_argument("--force-rollback", action="store_true")
    list_p = sub.add_parser("list")
    list_p.add_argument("--status")
    show_p = sub.add_parser("show")
    show_p.add_argument("--event-id", type=int, required=True)
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        if args.command in {"analyze", "apply"}:
            result = LawVersionImpactService(db).analyze(
                law_name=args.law_name,
                from_mst=args.from_mst,
                to_mst=args.to_mst,
                dry_run=args.command != "apply",
                force_rollback=args.force_rollback,
            )
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
            return 0 if result.status == "ok" else 1
        if args.command == "list":
            items = [
                {
                    "event_id": event.id,
                    "law_name": event.law_name,
                    "from_mst": event.from_mst,
                    "to_mst": event.to_mst,
                    "article_no": event.article_no,
                    "change_type": event.change_type,
                    "procedure_code": event.affected_procedure_code,
                    "impact_level": event.impact_level,
                    "review_status": event.derived_review_status,
                    "detected_at": event.detected_at,
                }
                for event in list_law_change_impact_events(db, status=args.status)
            ]
            print(json.dumps({"items": items, "count": len(items), "secret_exposed": False, "raw_payload_stored": False}, ensure_ascii=False, indent=2, default=str))
            return 0
        event = db.get(LawChangeImpactEvent, args.event_id)
        if event is None:
            print(json.dumps({"status": "not_found", "event_id": args.event_id}, ensure_ascii=False))
            return 1
        print(json.dumps({column.name: getattr(event, column.name) for column in LawChangeImpactEvent.__table__.columns}, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
