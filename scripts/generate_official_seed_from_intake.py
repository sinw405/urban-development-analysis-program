from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.official_law_seed_bootstrap_service import DEFAULT_SEED_DIR
from app.services.official_seed_intake_service import DEFAULT_SOURCE_MATERIAL_DIR, generate_official_seed_from_intake


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate sanitized official law seed YAML from reviewed Batch 1 intake files.")
    parser.add_argument("--path", "--source-dir", dest="source_dir", default=str(DEFAULT_SOURCE_MATERIAL_DIR), help="Directory containing source intake CSV/YAML files.")
    parser.add_argument("--seed-dir", dest="seed_dir", default=str(DEFAULT_SEED_DIR), help="Directory containing target seed YAML files.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plan seed generation without writing files. This is the default.")
    mode.add_argument("--apply", action="store_true", help="Write generated seed YAML files and validate the result.")
    args = parser.parse_args(argv)

    result = generate_official_seed_from_intake(source_dir=Path(args.source_dir), seed_dir=Path(args.seed_dir), apply=args.apply)
    result["path"] = str(Path(args.source_dir))
    result["seed_dir"] = str(Path(args.seed_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "validation_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())