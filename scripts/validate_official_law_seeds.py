from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.official_law_seed_bootstrap_service import DEFAULT_SEED_DIR, validate_official_law_seed_directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate sanitized manual official law seed YAML files.")
    parser.add_argument("--seed-dir", default=str(DEFAULT_SEED_DIR), help="Directory containing *.seed.yaml files.")
    parser.add_argument("--include-examples", action="store_true", help="Also validate files under examples/.")
    args = parser.parse_args(argv)

    report = validate_official_law_seed_directory(seed_dir=Path(args.seed_dir), include_examples=args.include_examples)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 1 if report.rejected_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
