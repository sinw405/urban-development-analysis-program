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
from app.services.moleg_live_ingest_service import run_moleg_live_ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run sanitized MOLEG live ingest for one official law.")
    parser.add_argument("--law-name", default="도시개발법")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plan live ingest without DB writes. Default.")
    mode.add_argument("--apply", action="store_true", help="Persist normalized live data in a transaction.")
    parser.add_argument("--force-rollback-after-persist", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    get_settings.cache_clear()
    dry_run = not args.apply

    db = SessionLocal()
    try:
        result = run_moleg_live_ingest(
            db=db,
            law_name=args.law_name,
            dry_run=dry_run,
            force_rollback_after_persist=args.force_rollback_after_persist,
        )
        payload = result.to_dict()
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 1 if payload["status"] in {"source_error", "rolled_back"} and payload["final_reason_type"] != "rollback_test" else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
