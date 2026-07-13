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
from app.services.moleg_version_diff_service import diff_moleg_versions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diff two stored MOLEG live law versions by MST.")
    parser.add_argument("--law-name", required=True)
    parser.add_argument("--from-mst", required=True)
    parser.add_argument("--to-mst", required=True)
    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        result = diff_moleg_versions(db=db, law_name=args.law_name, from_mst=args.from_mst, to_mst=args.to_mst)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
        return 0 if result.status == "ok" else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())