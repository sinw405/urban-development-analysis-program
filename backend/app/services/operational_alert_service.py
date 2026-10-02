from __future__ import annotations

import logging
import os
from typing import Any

from app.core.observability import log_event

logger = logging.getLogger(__name__)


def emit_operational_alert(event: str, *, severity: str = "warning", **fields: Any) -> None:
    """Emit an alert without coupling application operation to an external SaaS."""
    destination = os.getenv("OPERATIONAL_ALERT_DESTINATION", "").strip()
    level = logging.ERROR if severity.lower() in {"error", "critical"} else logging.WARNING
    # Phase 60-R deliberately supports only a structured-log destination.
    log_event(logger, level, "operational.alert", alert_event=event, severity=severity,
              destination=destination or "structured_log", **fields)
