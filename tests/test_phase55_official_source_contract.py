from datetime import date, datetime, UTC
from sqlalchemy import delete, select
from app.core.database import SessionLocal
from app.models import Law, LawArticle, LawArticleVersion, OfficialLawDocument
from app.services.legal_retrieval_service import build_legal_corpus

def test_official_source_url_uses_only_stored_allowlisted_moleg_url():
    key='PHASE55_URL_TEST_DO_NOT_USE'; mst='PHASE55-MST'
    with SessionLocal() as db:
        try:
            law=Law(law_name='PHASE55 TEST LAW', law_key=key, source='TEST', mapping_status='verified'); db.add(law); db.flush()
            article=LawArticle(law_id=law.id, article_key='A1', article_title='TEST ARTICLE', mapping_status='verified'); db.add(article); db.flush()
            db.add(LawArticleVersion(law_article_id=article.id, effective_date=date(2025,1,1), article_text='phase55 evidence', source='MOLEG_LIVE:'+mst, version_status='current'))
            db.add(OfficialLawDocument(source_provider='MOLEG',source_mode='live',law_title=law.law_name,law_id=key,mst=mst,enforcement_date=date(2025,1,1),is_current=True,document_status='normalized',normalized_at=datetime.now(UTC),sanitized_source_url='https://www.law.go.kr/stored-official'))
            db.commit(); item=next(x for x in build_legal_corpus(db,date(2026,1,1),{'article'}) if x.law_identifier==key)
            assert item.provenance['official_source_url']=='https://www.law.go.kr/stored-official'
        finally:
            law=db.scalar(select(Law).where(Law.law_key==key))
            if law:
                ids=list(db.scalars(select(LawArticle.id).where(LawArticle.law_id==law.id)))
                if ids: db.execute(delete(LawArticleVersion).where(LawArticleVersion.law_article_id.in_(ids))); db.execute(delete(LawArticle).where(LawArticle.id.in_(ids)))
                db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.mst==mst)); db.delete(law); db.commit()
