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
from app.services.official_law_seed_bootstrap_service import DEFAULT_SEED_DIR, import_official_law_seed_directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import sanitized manual official law seed YAML files into the official law DB snapshot.")
    parser.add_argument("--seed-dir", default=str(DEFAULT_SEED_DIR), help="Directory containing *.seed.yaml files.")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        result = import_official_law_seed_directory(db=db, seed_dir=Path(args.seed_dir))
    finally:
        db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "validation_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
