from pathlib import Path
import sys

from alembic import command
from alembic.config import Config

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def pytest_sessionstart(session):
    alembic_cfg = Config(str(ROOT_DIR / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
