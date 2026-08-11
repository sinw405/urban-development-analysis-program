import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)

def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    return default if raw_value is None else raw_value.strip().lower() in {"1", "true", "yes", "on"}

def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip(): return default
    try: return float(raw_value)
    except ValueError: return default

def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip(): return default
    try: return int(raw_value)
    except ValueError: return default

class Settings:
    app_name = "Urban Development Analysis API"
    project_root = PROJECT_ROOT
    @property
    def database_url(self) -> str: return os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/urban_dev")
    @property
    def rules_dir(self) -> Path: return self.project_root / "rules"
    @property
    def cors_allowed_origins(self) -> list[str]:
        return [item.strip() for item in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if item.strip()]
    @property
    def moleg_api_base_url(self) -> str: return os.getenv("MOLEG_API_BASE_URL", "").strip()
    @property
    def moleg_api_key(self) -> str: return (os.getenv("MOLEG_API_KEY") or os.getenv("MOLEG_OC") or "").strip()
    @property
    def moleg_api_timeout_seconds(self) -> float: return _env_float("MOLEG_API_TIMEOUT_SECONDS", 5.0)
    @property
    def moleg_api_enabled(self) -> bool: return _env_flag("MOLEG_API_ENABLED", False)
    @property
    def moleg_live_test_enabled(self) -> bool: return _env_flag("MOLEG_LIVE_TEST_ENABLED", False)
    @property
    def moleg_api_configured(self) -> bool: return self.moleg_api_enabled and bool(self.moleg_api_base_url) and bool(self.moleg_api_key)
    @property
    def moleg_live_test_configured(self) -> bool: return self.moleg_live_test_enabled and self.moleg_api_configured
    @property
    def law_update_scheduler_enabled(self) -> bool: return _env_flag("LAW_UPDATE_SCHEDULER_ENABLED", False)
    @property
    def law_update_scheduler_interval_hours(self) -> float:
        value=_env_float("LAW_UPDATE_SCHEDULER_INTERVAL_HOURS",24.0)
        if value<=0: raise ValueError("LAW_UPDATE_SCHEDULER_INTERVAL_HOURS must be greater than zero")
        return value
    @property
    def law_update_scheduler_retry_count(self) -> int:
        value=_env_int("LAW_UPDATE_SCHEDULER_RETRY_COUNT",1)
        if value<0 or value>2: raise ValueError("LAW_UPDATE_SCHEDULER_RETRY_COUNT must be between zero and two")
        return value
    @property
    def law_update_scheduler_retry_backoff_seconds(self) -> float:
        value=_env_float("LAW_UPDATE_SCHEDULER_RETRY_BACKOFF_SECONDS",0.25)
        if value<0: raise ValueError("LAW_UPDATE_SCHEDULER_RETRY_BACKOFF_SECONDS must not be negative")
        return value

@lru_cache
def get_settings() -> Settings: return Settings()