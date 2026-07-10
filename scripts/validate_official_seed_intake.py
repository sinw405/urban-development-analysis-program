from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.official_seed_intake_service import DEFAULT_SOURCE_MATERIAL_DIR, validate_official_seed_intake


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate sanitized official seed Batch 1 intake files.")
    parser.add_argument("--path", "--source-dir", dest="source_dir", default=str(DEFAULT_SOURCE_MATERIAL_DIR), help="Directory containing source intake CSV/YAML files.")
    args = parser.parse_args(argv)

    report = validate_official_seed_intake(source_dir=Path(args.source_dir))
    payload = report.to_dict()
    payload["path"] = payload["source_material_directory"]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if report.rejected_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())