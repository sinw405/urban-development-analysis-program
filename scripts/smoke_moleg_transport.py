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
from app.services.moleg_live_client import DEFAULT_LIVE_QUERY
from app.services.moleg_probe_service import run_moleg_live_probes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run sanitized MOLEG Open API live probes.")
    parser.add_argument("--probe", choices=["config", "network", "search", "detail", "parse", "storage_policy", "all"], default="all")
    parser.add_argument("--query", default=DEFAULT_LIVE_QUERY)
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    get_settings.cache_clear()
    try:
        diagnostic = run_moleg_live_probes(probe=args.probe, query=args.query)
    except Exception as exc:
        print(json.dumps({"status": "error", "final_reason_type": "code_error", "error_class": exc.__class__.__name__, "secret_exposed": False, "raw_payload_stored": False}, ensure_ascii=False))
        return 1

    status = "ok" if diagnostic.transport_ok else "source_error"
    if diagnostic.final_reason_type in {"live_disabled", "not_configured"}:
        status = "skipped"

    payload = {
        "status": status,
        "probe": args.probe,
        "probe_results": [item.model_dump() for item in diagnostic.probe_results],
        "final_reason_type": diagnostic.final_reason_type or diagnostic.reason_type,
        "reason_type": diagnostic.final_reason_type or diagnostic.reason_type,
        "reason_message_ko": diagnostic.reason_message_ko or diagnostic.reason_message,
        "suggested_fix": diagnostic.suggested_fix or diagnostic.next_action,
        "transport_ok": diagnostic.transport_ok,
        "search_ok": diagnostic.search_ok,
        "detail_ok": diagnostic.detail_ok,
        "parse_ok": diagnostic.parse_ok,
        "secret_exposed": diagnostic.secret_exposed,
        "raw_payload_stored": diagnostic.raw_payload_stored,
        "fallback_available": diagnostic.fallback_available,
        "fallback_source_modes": diagnostic.fallback_source_modes,
        "response_format": diagnostic.response_format,
        "sample_law_count": diagnostic.sample_law_count,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())