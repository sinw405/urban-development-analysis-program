from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
from sqlalchemy import func, select

from app.core.config import PROJECT_ROOT, get_settings
from app.core.database import SessionLocal
from app.models import LiveLawChangeEvent, LiveLawChangeEventAudit
from app.services.live_law_change_persistence_service import execute_phase43
from app.services.moleg_live_client import MOLEG_LAW_SEARCH_PATH, MolegLiveClient, _parse_response_payload
from app.services.moleg_version_discovery_service import (
    discover_law_versions,
    eflaw_search_params,
    parse_eflaw_list_response,
)

LAW_NAME = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
REPORT_FIELDS = [
    "environment", "MOLEG credential present", "HTTP status", "resultCode", "resultMsg", "totalCnt",
    "requested pages", "collected items", "exact law versions", "from_mst", "to_mst",
    "from_effective_date", "to_effective_date", "from_article_count", "to_article_count",
    "version_changed", "content_changed", "changed_article_count", "added_count", "removed_count",
    "modified_count", "impacted_rule_count", "analysis_status", "event_id", "idempotency_key",
    "event_count_after_second_run", "idempotency_passed", "audit_history_count", "parser_warning",
    "secret_exposed", "FINAL RESULT",
]


def empty_report() -> dict[str, Any]:
    report = {field: None for field in REPORT_FIELDS}
    report.update({
        "environment": "local_live",
        "MOLEG credential present": False,
        "requested pages": [],
        "parser_warning": [],
        "secret_exposed": False,
        "FINAL RESULT": "FAIL: unknown",
    })
    return report


def fail(report: dict[str, Any], category: str) -> int:
    report["FINAL RESULT"] = f"FAIL: {category}"
    print(render_report(report))
    return 1


def render_report(report: dict[str, Any]) -> str:
    lines = ["PHASE 43 LOCAL LIVE ACCEPTANCE", ""]
    for index, field in enumerate(REPORT_FIELDS, 1):
        value = report.get(field)
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False, default=str)
        lines.append(f"{index}. {field}: {value}")
    return "\n".join(lines)


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    get_settings.cache_clear()
    settings = get_settings()
    report = empty_report()
    report["MOLEG credential present"] = bool(settings.moleg_api_key)
    if not settings.moleg_api_configured:
        return fail(report, "credential")

    client = MolegLiveClient()
    try:
        params = eflaw_search_params(client, LAW_NAME, display=1, page=1)
        response = client._request(MOLEG_LAW_SEARCH_PATH, params)
        search = parse_eflaw_list_response(_parse_response_payload(response))
        report.update({
            "HTTP status": response.status_code,
            "resultCode": search.get("result_code"),
            "resultMsg": search.get("result_msg"),
            "totalCnt": search.get("total_cnt"),
        })
        if response.status_code != 200 or search.get("result_code") not in {None, "00", "0"} or not search.get("laws"):
            return fail(report, "discovery")
    except Exception:
        return fail(report, "network")

    try:
        discovery = discover_law_versions(client, LAW_NAME, max_versions=200)
        report.update({
            "requested pages": discovery.requested_pages,
            "collected items": discovery.collected_item_count,
            "exact law versions": discovery.exact_match_count,
            "parser_warning": discovery.warnings,
        })
        if discovery.status != "ok" or discovery.selection is None:
            return fail(report, "discovery")
        selection = discovery.selection
        report.update({
            "from_mst": selection.from_mst,
            "to_mst": selection.to_mst,
            "from_effective_date": selection.from_version.enforcement_date,
            "to_effective_date": selection.to_version.enforcement_date,
        })
    except Exception:
        return fail(report, "discovery")

    try:
        with SessionLocal() as db:
            first = execute_phase43(db, client, selection, ensure_versions=True, persist_event=True)
            if first.status != "ok":
                category = _phase_failure_category(first.analysis_status, first.errors)
                return fail(report, category)
            second = execute_phase43(db, client, selection, ensure_versions=True, persist_event=True)
            event = second.event or first.event
            if event is None:
                return fail(report, "event_persistence")
            event_count = db.scalar(
                select(func.count()).select_from(LiveLawChangeEvent)
                .where(LiveLawChangeEvent.idempotency_key == event.idempotency_key)
            ) or 0
            audits = list(db.scalars(
                select(LiveLawChangeEventAudit)
                .where(LiveLawChangeEventAudit.event_id == event.id)
                .order_by(LiveLawChangeEventAudit.id)
            ).all())
            states = second.version_states or first.version_states
            changes = second.changed_articles
            counts = {kind: sum(1 for item in changes if item.get("change_type") == kind) for kind in ("added", "removed", "modified")}
            idempotent = bool(first.event and second.event and first.event.id == second.event.id and event_count == 1)
            report.update({
                "from_article_count": states[0].article_count if len(states) > 0 else None,
                "to_article_count": states[1].article_count if len(states) > 1 else None,
                "version_changed": second.version_changed,
                "content_changed": second.content_changed,
                "changed_article_count": len(changes),
                "added_count": counts["added"],
                "removed_count": counts["removed"],
                "modified_count": counts["modified"],
                "impacted_rule_count": len(second.impacted_rules),
                "analysis_status": second.analysis_status,
                "event_id": event.id,
                "idempotency_key": event.idempotency_key,
                "event_count_after_second_run": event_count,
                "idempotency_passed": idempotent,
                "audit_history_count": len(audits),
            })
            if not idempotent:
                return fail(report, "idempotency")
    except Exception:
        return fail(report, "database")

    report["FINAL RESULT"] = "PASS"
    print(render_report(report))
    return 0


def _phase_failure_category(status: str, errors: list[str]) -> str:
    text = " ".join([status, *errors]).lower()
    if "ingest" in text or "missing_version" in text:
        return "ingest"
    if "parse" in text or "incomplete_version" in text:
        return "parsing"
    if "analysis" in text or "diff" in text:
        return "diff"
    return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
