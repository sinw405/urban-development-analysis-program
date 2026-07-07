from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _delete_test_legal_reference_rows() -> None:
    from app.core.database import SessionLocal
    from app.models import Law, LawArticle, LawArticleVersion, LawUpdateEvent, ProcedureLegalReference

    db = SessionLocal()
    try:
        law_ids = list(db.scalars(select(Law.id).where(Law.law_name.like("TEST_%_DO_NOT_USE"))).all())
        if not law_ids:
            return

        article_ids = list(db.scalars(select(LawArticle.id).where(LawArticle.law_id.in_(law_ids))).all())
        db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_id.in_(law_ids)))
        db.execute(delete(LawUpdateEvent).where(LawUpdateEvent.law_id.in_(law_ids)))
        if article_ids:
            db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(article_ids)))
            db.execute(delete(ProcedureLegalReference).where(ProcedureLegalReference.law_article_id.in_(article_ids)))
            db.execute(delete(LawArticle).where(LawArticle.id.in_(article_ids)))
        db.execute(delete(Law).where(Law.id.in_(law_ids)))
        db.commit()
    finally:
        db.close()


def pytest_sessionstart(session):
    alembic_cfg = Config(str(ROOT_DIR / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    _delete_test_legal_reference_rows()
