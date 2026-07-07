from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Law, LawArticle, LawArticleVersion, ProcedureLegalReference
from app.services.legal_reference_service import (
    PENDING_MOLEG_API_MAPPING,
    TODO_MOLEG_API_ARTICLE_CHECK,
)


def test_legal_reference_models_can_be_created_and_queried():
    db = SessionLocal()
    try:
        law = Law(
            law_name="TEST_LAW_DO_NOT_USE",
            source="TEST_SOURCE_DO_NOT_USE",
            mapping_status=PENDING_MOLEG_API_MAPPING,
        )
        db.add(law)
        db.flush()

        article = LawArticle(
            law_id=law.id,
            article_key="TEST_ARTICLE_KEY_DO_NOT_USE",
            article_number_text="TEST_ARTICLE_DO_NOT_USE",
            article_title="TEST_ARTICLE_TITLE_DO_NOT_USE",
            mapping_status=TODO_MOLEG_API_ARTICLE_CHECK,
        )
        db.add(article)
        db.flush()

        version = LawArticleVersion(
            law_article_id=article.id,
            source="TEST_SOURCE_DO_NOT_USE",
            version_status=PENDING_MOLEG_API_MAPPING,
        )
        reference = ProcedureLegalReference(
            step_code="TEST_STEP_DO_NOT_USE",
            law_id=law.id,
            law_article_id=article.id,
            reference_status=TODO_MOLEG_API_ARTICLE_CHECK,
            placeholder=TODO_MOLEG_API_ARTICLE_CHECK,
            notes_json={"status": "TEST_PENDING_DO_NOT_USE"},
        )
        db.add_all([version, reference])
        db.commit()

        stored = db.scalar(select(ProcedureLegalReference).where(ProcedureLegalReference.id == reference.id))

        assert stored is not None
        assert stored.step_code == "TEST_STEP_DO_NOT_USE"
        assert stored.reference_status == TODO_MOLEG_API_ARTICLE_CHECK
        assert stored.placeholder == TODO_MOLEG_API_ARTICLE_CHECK
        assert stored.law is not None
        assert stored.law.law_name == "TEST_LAW_DO_NOT_USE"
        assert stored.law.mapping_status == PENDING_MOLEG_API_MAPPING
        assert stored.law_article is not None
        assert stored.law_article.article_number_text == "TEST_ARTICLE_DO_NOT_USE"
    finally:
        db.close()
