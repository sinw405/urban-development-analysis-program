from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

REDACTED = "[REDACTED]"
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_SENSITIVE_KEY = re.compile(r"(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|credential|postgres_password)$", re.I)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT = re.compile(r"(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|credential|postgres_password)\s*([=:])\s*([^\s,;]+)")
_URL = re.compile(r"(?i)\b(?:postgres(?:ql)?(?:\+[a-z0-9]+)?|https?)://[^\s]+")


def correlation_id() -> str | None:
    return _correlation_id.get()


def bind_correlation_id(value: str) -> Token:
    return _correlation_id.set(value)


def reset_correlation_id(token: Token) -> None:
    _correlation_id.reset(token)


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.password is None:
            return value
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
        user = parsed.username or ""
        return urlunsplit((parsed.scheme, f"{user}:{REDACTED}@{host}", parsed.path, parsed.query, parsed.fragment))
    except (TypeError, ValueError):
        return REDACTED


def redact(value: Any, key: str | None = None) -> Any:
    if key and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(item) for item in value]
    if isinstance(value, BaseException):
        value = f"{value.__class__.__name__}: {value}"
    if not isinstance(value, str):
        return value
    text = _BEARER.sub(f"Bearer {REDACTED}", value)
    text = _ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", text)
    text = _URL.sub(lambda match: _redact_url(match.group(0)), text)
    return text


class StructuredJsonFormatter(logging.Formatter):
    _reserved = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
            "component": record.name,
        }
        request_id = getattr(record, "correlation_id", None) or correlation_id()
        if request_id:
            payload["correlation_id"] = request_id
        for name, value in record.__dict__.items():
            if name not in self._reserved and name not in {"event", "correlation_id"} and not name.startswith("_"):
                payload[name] = value
        if record.exc_info:
            payload["error_category"] = record.exc_info[0].__name__
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(redact(payload), ensure_ascii=False, default=str, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    include_exception = bool(fields.pop("exc_info", False))
    logger.log(level, event, extra={"event": event, **redact(fields)}, exc_info=include_exception)
