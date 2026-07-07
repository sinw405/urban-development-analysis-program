import os
from functools import lru_cache
from pathlib import Path


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    app_name = "Urban Development Analysis API"
    project_root = Path(__file__).resolve().parents[3]

    @property
    def database_url(self) -> str:
        return os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5433/urban_dev",
        )

    @property
    def rules_dir(self) -> Path:
        return self.project_root / "rules"

    @property
    def moleg_api_base_url(self) -> str:
        return os.getenv("MOLEG_API_BASE_URL", "")

    @property
    def moleg_api_key(self) -> str:
        return os.getenv("MOLEG_API_KEY", "")

    @property
    def moleg_api_enabled(self) -> bool:
        return _env_flag("MOLEG_API_ENABLED", default=False)

    @property
    def moleg_api_configured(self) -> bool:
        return self.moleg_api_enabled and bool(self.moleg_api_base_url) and bool(self.moleg_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
