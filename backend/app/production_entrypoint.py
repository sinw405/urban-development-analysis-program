from __future__ import annotations

import os
from urllib.parse import urlsplit

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FORBIDDEN_PRODUCTION_FLAGS = (
    "DEBUG",
    "MOLEG_LIVE_TEST_ENABLED",
    "TEST_FIXTURE_ENABLED",
    "LOAD_TEST_FIXTURES",
    "AUTO_SEED",
)


def validate_production_environment() -> None:
    if os.getenv("APP_ENV", "").strip().lower() != "production":
        raise RuntimeError("APP_ENV must be production")
    enabled = [
        name
        for name in _FORBIDDEN_PRODUCTION_FLAGS
        if os.getenv(name, "false").strip().lower() in _TRUE_VALUES
    ]
    if enabled:
        raise RuntimeError(f"Production-only safety flags must be disabled: {', '.join(enabled)}")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required in production")
    parsed = urlsplit(database_url)
    if parsed.hostname in {None, "localhost", "127.0.0.1"}:
        raise RuntimeError("Production DATABASE_URL must not use a development host")
    if parsed.password in {None, "", "postgres", "REPLACE_WITH_EXTERNAL_SECRET"}:
        raise RuntimeError("Production DATABASE_URL must use an external non-placeholder secret")


def main() -> None:
    validate_production_environment()
    if len(os.sys.argv) == 2 and os.sys.argv[1] == "migrate":
        os.execvp("alembic", ["alembic", "upgrade", "head"])
    if len(os.sys.argv) != 1:
        raise RuntimeError("production entrypoint accepts only the optional migrate command")
    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    )


if __name__ == "__main__":
    main()

