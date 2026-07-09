from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.procedure_article_candidate_service import validate_seed_candidate_items

DEFAULT_SEED_PATH = Path("rules/procedure_article_seed_candidates.json")


def load_seed_items(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload["items"]
    raise ValueError("seed file must be a JSON list or an object with an items list")


def validate_seed_file(path: Path) -> list[str]:
    items = load_seed_items(path)
    return validate_seed_candidate_items(items)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate procedure article seed candidate files without storing raw legal payloads.")
    parser.add_argument("--path", default=str(DEFAULT_SEED_PATH), help="Path to a JSON seed candidate file. Defaults to rules/procedure_article_seed_candidates.json")
    args = parser.parse_args(argv)
    path = Path(args.path)
    if not path.exists():
        print(f"seed validation skipped: {path} does not exist")
        return 0
    try:
        errors = validate_seed_file(path)
    except Exception as exc:  # noqa: BLE001 - CLI should present validation failures plainly.
        print(f"seed validation failed: {type(exc).__name__}: {exc}")
        return 1
    if errors:
        print("seed validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"seed validation passed: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
