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
from app.services.official_law_seed_bootstrap_service import DEFAULT_SEED_DIR, import_official_law_seed_directory, plan_official_law_seed_import


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import sanitized manual official law seed YAML files into the official law DB snapshot.")
    parser.add_argument("--path", "--seed-dir", dest="seed_dir", default=str(DEFAULT_SEED_DIR), help="Directory containing seed YAML files.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report planned import counts without writing to the database.")
    args = parser.parse_args(argv)

    seed_dir = Path(args.seed_dir)
    if args.dry_run:
        result = plan_official_law_seed_import(seed_dir=seed_dir)
    else:
        db = SessionLocal()
        try:
            result = import_official_law_seed_directory(db=db, seed_dir=seed_dir)
        finally:
            db.close()
    result["path"] = str(seed_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "validation_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())