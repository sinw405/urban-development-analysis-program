from pathlib import Path
import pytest
from app.production_entrypoint import validate_production_environment

FLAGS = ("DEBUG", "MOLEG_LIVE_TEST_ENABLED", "TEST_FIXTURE_ENABLED", "LOAD_TEST_FIXTURES", "AUTO_SEED")

def safe(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app:external-secret@postgres:5432/prod")
    for name in FLAGS:
        monkeypatch.setenv(name, "false")

def test_safe_production_environment(monkeypatch):
    safe(monkeypatch)
    validate_production_environment()

@pytest.mark.parametrize("name", FLAGS)
def test_unsafe_flags_are_rejected(monkeypatch, name):
    safe(monkeypatch)
    monkeypatch.setenv(name, "true")
    with pytest.raises(RuntimeError, match=name):
        validate_production_environment()

@pytest.mark.parametrize("url", ["", "postgresql+psycopg://app:secret@localhost:5432/prod", "postgresql+psycopg://postgres:postgres@postgres:5432/prod"])
def test_unsafe_databases_are_rejected(monkeypatch, url):
    safe(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError):
        validate_production_environment()

def test_deployment_files_are_production_safe():
    compose = Path("compose.prod.yml").read_text(encoding="utf-8-sig")
    assert "app.dev_seed" not in compose and "--reload" not in compose
    assert "elasticsearch" not in compose.lower() and "redis:" not in compose.lower()
    assert "service_completed_successfully" in compose
    assert 'app.production_entrypoint", "migrate"' in compose
    assert 'AUTO_SEED: "false"' in compose
    dockerfile = Path("frontend/Dockerfile").read_text(encoding="utf-8-sig")
    nginx = Path("frontend/nginx.conf").read_text(encoding="utf-8-sig")
    assert "npm ci" in dockerfile and "npm run build" in dockerfile
    assert "location /api/" in nginx and "proxy_pass http://backend:8000" in nginx

