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
from app.services.procedure_article_review_service import candidate_detail, confirm_candidate, list_review_candidates, reject_candidate, reopen_candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review procedure to official article candidates without exposing secrets or raw payloads.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--status", choices=["unconfirmed", "confirmed", "rejected", "needs_revalidation", "stale"], default=None)

    show_parser = sub.add_parser("show")
    show_parser.add_argument("--candidate-id", type=int, required=True)

    for name in ["confirm", "reject", "reopen"]:
        action = sub.add_parser(name)
        action.add_argument("--candidate-id", type=int, required=True)
        action.add_argument("--reviewer", required=True)
        action.add_argument("--note", required=True)
        action.add_argument("--force-rollback", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        if args.command == "list":
            payload = {"items": list_review_candidates(db, status=args.status), "secret_exposed": False, "raw_payload_stored": False}
            code = 0
        elif args.command == "show":
            payload = candidate_detail(db, args.candidate_id)
            code = 0
        elif args.command == "confirm":
            result = confirm_candidate(db, args.candidate_id, args.reviewer, args.note, force_rollback=args.force_rollback)
            payload = result.to_dict()
            code = 0 if result.status == "ok" or result.status == "rolled_back" and result.rollback else 1
        elif args.command == "reject":
            result = reject_candidate(db, args.candidate_id, args.reviewer, args.note, force_rollback=args.force_rollback)
            payload = result.to_dict()
            code = 0 if result.status == "ok" or result.status == "rolled_back" and result.rollback else 1
        else:
            result = reopen_candidate(db, args.candidate_id, args.reviewer, args.note, force_rollback=args.force_rollback)
            payload = result.to_dict()
            code = 0 if result.status == "ok" or result.status == "rolled_back" and result.rollback else 1
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return code
    except ValueError as exc:
        print(json.dumps({"status": "not_found", "reason": str(exc), "secret_exposed": False, "raw_payload_stored": False}, ensure_ascii=False, indent=2))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())