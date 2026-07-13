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

from app.core.config import PROJECT_ROOT, get_settings
from app.core.database import SessionLocal
from app.services.moleg_live_ingest_service import LAW_FAMILY_URBAN_DEVELOPMENT, run_moleg_law_family_ingest, run_moleg_live_ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run sanitized MOLEG live ingest for one official law or a configured law family.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--law-name", default=None)
    target.add_argument("--law-family", choices=[LAW_FAMILY_URBAN_DEVELOPMENT], default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plan live ingest without DB writes. Default.")
    mode.add_argument("--apply", action="store_true", help="Persist normalized live data in per-law transactions.")
    parser.add_argument("--include-history", type=int, default=0, help="Number of immediately previous exact-match versions to ingest when MOLEG search exposes them.")
    parser.add_argument("--force-rollback-after-persist", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    get_settings.cache_clear()
    dry_run = not args.apply

    if args.law_family:
        result = run_moleg_law_family_ingest(
            db_factory=SessionLocal,
            law_family=args.law_family,
            dry_run=dry_run,
            include_history=max(0, args.include_history),
            force_rollback_after_persist=args.force_rollback_after_persist,
        )
        payload = result.to_dict()
    else:
        db = SessionLocal()
        try:
            result = run_moleg_live_ingest(
                db=db,
                law_name=args.law_name or "도시개발법",
                dry_run=dry_run,
                force_rollback_after_persist=args.force_rollback_after_persist,
                include_history=max(0, args.include_history),
            )
            payload = result.to_dict()
        finally:
            db.close()

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    rollback_test = payload.get("final_reason_type") == "rollback_test" or all(item.get("final_reason_type") == "rollback_test" for item in payload.get("results", []))
    failed = payload.get("status") in {"source_error", "rolled_back", "failed", "unknown_law_family"}
    return 1 if failed and not rollback_test else 0


if __name__ == "__main__":
    raise SystemExit(main())