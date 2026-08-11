from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
from sqlalchemy import select

from app.core.config import PROJECT_ROOT, get_settings
from app.core.database import SessionLocal
from app.models import Law, ProcedureLegalReference
from app.services.assessment_reference_seed_service import apply_assessment_reference_seeds
from app.services.moleg_live_client import MOLEG_LAW_SEARCH_PATH, MolegLiveClient, _parse_response_payload
from app.services.moleg_version_discovery_service import eflaw_search_params, parse_eflaw_list_response
from app.services.rule_loader import load_yaml_rule


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify and optionally apply Phase 46.5 assessment legal references.")
    parser.add_argument("--apply", action="store_true", help="Persist verified seed references after all evidence checks pass.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--trust-env", choices=("true", "false"), default="false")
    args = parser.parse_args(argv)
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    get_settings.cache_clear()
    settings = get_settings()
    report = {
        "environment": "local_live",
        "moleg_configured": settings.moleg_api_configured,
        "live_search_success": False,
        "apply": args.apply,
        "trust_env": args.trust_env == "true",
        "as_of": str(args.as_of),
        "seed_status": None,
        "created_count": 0,
        "existing_count": 0,
        "unresolved_count": 0,
        "assessments": [],
        "secret_exposed": False,
        "FINAL RESULT": "FAIL: unknown",
    }
    if not settings.moleg_api_configured:
        return _finish(report, "FAIL: credential")

    seeds = load_yaml_rule("assessment_legal_reference_seeds.yaml").get("references", [])
    try:
        client = MolegLiveClient(
            timeout_seconds=settings.moleg_api_timeout_seconds,
            retry_count=0,
            trust_env=args.trust_env == "true",
        )
        with SessionLocal() as db:
            for seed in seeds:
                law = db.scalar(select(Law).where(Law.law_key == seed["law_key"]))
                if law is None:
                    continue
                response = client._request(
                    MOLEG_LAW_SEARCH_PATH,
                    eflaw_search_params(client, law.law_name, display=10, page=1),
                )
                parsed = parse_eflaw_list_response(_parse_response_payload(response))
                exact = [item for item in parsed.get("laws", []) if item.get("law_name") == law.law_name]
                if response.status_code != 200 or parsed.get("result_code") not in {None, "0", "00"} or not exact:
                    return _finish(report, "FAIL: discovery")
        report["live_search_success"] = True
    except Exception:
        return _finish(report, "FAIL: network")

    try:
        with SessionLocal() as db:
            seeded = apply_assessment_reference_seeds(db, apply=args.apply, as_of=args.as_of)
            report.update(
                seed_status=seeded.status,
                created_count=seeded.created_count,
                existing_count=seeded.existing_count,
                unresolved_count=seeded.unresolved_count,
            )
        with SessionLocal() as db:
            rules = load_yaml_rule("assessment_rules.yaml")["assessment_items"]
            references = list(db.scalars(select(ProcedureLegalReference)).all())
            for rule in rules:
                matching = [ref for ref in references if ref.step_code == rule["assessment_code"]]
                verified = any((ref.notes_json or {}).get("reference_quality") == "verified" for ref in matching)
                report["assessments"].append({
                    "assessment_code": rule["assessment_code"],
                    "legal_basis_status": "verified" if verified else rule["legal_basis_status"],
                    "applicability_status": rule.get("applicability_status", "unresolved"),
                    "threshold_status": rule.get("threshold_status", "placeholder"),
                    "reference_count": len(matching),
                })
    except Exception:
        return _finish(report, "FAIL: database")

    if report["unresolved_count"]:
        return _finish(report, "UNRESOLVED: seed evidence")
    return _finish(report, "PASS")


def _finish(report: dict, result: str) -> int:
    report["FINAL RESULT"] = result
    print(render_report(report))
    return 0 if result == "PASS" else 1


def render_report(report: dict) -> str:
    safe = dict(report)
    safe["secret_exposed"] = False
    return "PHASE 46.5 ASSESSMENT LIVE LEGAL GROUNDING\n\n" + json.dumps(
        safe, ensure_ascii=False, indent=2, default=str
    )


if __name__ == "__main__":
    raise SystemExit(main())
