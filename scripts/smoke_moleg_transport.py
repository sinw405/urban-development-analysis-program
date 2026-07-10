from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

from app.core.config import PROJECT_ROOT, get_settings
from app.services.moleg_diagnostic_service import diagnose_moleg_safe


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    get_settings.cache_clear()
    try:
        diagnostic = diagnose_moleg_safe()
    except Exception as exc:
        print(json.dumps({"status": "error", "reason_type": "code_error", "error_class": exc.__class__.__name__}, ensure_ascii=False))
        return 1

    status = "ok" if diagnostic.transport_ok else "source_error"
    if diagnostic.reason_type in {"live_disabled", "not_configured"}:
        status = "skipped"

    print(
        json.dumps(
            {
                "status": status,
                "live_enabled": diagnostic.live_enabled,
                "configured": diagnostic.configured,
                "transport_ok": diagnostic.transport_ok,
                "reason_type": diagnostic.reason_type,
                "reason_message": diagnostic.reason_message,
                "secret_exposed": diagnostic.secret_exposed,
                "raw_payload_stored": diagnostic.raw_payload_stored,
                "request_sanitized": diagnostic.request_sanitized,
                "fallback_available": diagnostic.fallback_available,
                "fallback_source_modes": diagnostic.fallback_source_modes,
                "response_format": diagnostic.response_format,
                "sample_law_count": diagnostic.sample_law_count,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


