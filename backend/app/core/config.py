import os
from functools import lru_cache
from pathlib import Path


class Settings:
    app_name = "Urban Development Analysis API"
    project_root = Path(__file__).resolve().parents[3]

    @property
    def database_url(self) -> str:
        return os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@postgres:5432/urban_dev",
        )

    @property
    def rules_dir(self) -> Path:
        return self.project_root / "rules"


@lru_cache
def get_settings() -> Settings:
    return Settings()
