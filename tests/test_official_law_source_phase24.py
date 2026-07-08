from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.models import OfficialLawArticleRecord, OfficialLawDocument, OfficialLawIngestRun, OfficialLawSourceEvidence
from app.services.moleg_diagnostic_service import diagnose_moleg_connectivity
from app.services.official_law_persistence_service import (
    INGEST_STATUS_SOURCE_ERROR,
    complete_ingest_run,
    create_ingest_run,
    ingest_fixture_document,
)
from app.services.official_law_source import MolegOpenApiLawSourceProvider

SECRET = "TEST_PHASE24_SECRET_DO_NOT_USE"
URBAN_DEVELOPMENT_LAW = "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"
ARTICLE_3 = "\uc81c3\uc870"

SEARCH_FIXTURE = {
    "LawSearch": {
        "totalCnt": "1",
        "page": "1",
        "display": "20",
        "law": [
            {
                "\ubc95\ub839\uba85\ud55c\uae00": URBAN_DEVELOPMENT_LAW,
                "\ubc95\ub839\uc57d\uce6d\uba85": URBAN_DEVELOPMENT_LAW,
                "MST": "241111",
                "\ubc95\ub839ID": "240001",
                "\uacf5\ud3ec\uc77c\uc790": "20220101",
                "\uc2dc\ud589\uc77c\uc790": "20240223",
                "\ud604\ud589\uc5ec\ubd80": "\ud604\ud589",
                "OC": SECRET,
            }
        ],
    }
}

DOCUMENT_FIXTURE = {
    "\ubc95\ub839": {
        "\uae30\ubcf8\uc815\ubcf4": {
            "\ubc95\ub839\uba85\ud55c\uae00": URBAN_DEVELOPMENT_LAW,
            "\ubc95\ub839ID": "240001",
            "\uc2dc\ud589\uc77c\uc790": "20240223",
        },
        "\uc870\ubb38": {
            "\uc870\ubb38\ub2e8\uc704": [
                {
                    "\uc870\ubb38\ubc88\ud638": ARTICLE_3,
                    "\uc870\ubb38\uc81c\ubaa9": "\ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815 \ub4f1",
                    "\uc870\ubb38\ub0b4\uc6a9": "\uc81c3\uc870 \ub3c4\uc2dc\uac1c\ubc1c\uad6c\uc5ed\uc758 \uc9c0\uc815\uc5d0 \uad00\ud55c \ub0b4\uc6a9",
                    "\ud56d": [{"\ud56d\ub0b4\uc6a9": "\u2460 \uc9c0\uc815\uad8c\uc790\ub294 \uc9c0\uc815\ud560 \uc218 \uc788\ub2e4."}],
                },
                {
                    "\uc870\ubb38\ubc88\ud638": "\uc81c4\uc870",
                    "\uc870\ubb38\uc81c\ubaa9": "\uac1c\ubc1c\uacc4\ud68d\uc758 \uc218\ub9bd",
                    "\uc870\ubb38\ub0b4\uc6a9": "\uc81c4\uc870 \uac1c\ubc1c\uacc4\ud68d\uc758 \uc218\ub9bd\uc5d0 \uad00\ud55c \ub0b4\uc6a9",
                },
            ]
        },
    }
}


def _cleanup_phase24_rows():
    db = SessionLocal()
    try:
        run_ids = list(db.scalars(select(OfficialLawIngestRun.id).where(OfficialLawIngestRun.query == URBAN_DEVELOPMENT_LAW)).all())
        if run_ids:
            db.execute(delete(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id.in_(run_ids)))
            db.execute(delete(OfficialLawIngestRun).where(OfficialLawIngestRun.id.in_(run_ids)))
        document_ids = list(db.scalars(select(OfficialLawDocument.id).where(OfficialLawDocument.mst == "241111")).all())
        if document_ids:
            db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id.in_(document_ids)))
            db.execute(delete(OfficialLawDocument).where(OfficialLawDocument.id.in_(document_ids)))
        db.commit()
    finally:
        db.close()


def test_fixture_document_is_persisted_with_articles_ingest_run_and_evidence():
    _cleanup_phase24_rows()
    db = SessionLocal()
    try:
        provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)
        search_result = provider._normalize_law_search_result(SEARCH_FIXTURE, query=URBAN_DEVELOPMENT_LAW)
        document = provider._normalize_law_document(DOCUMENT_FIXTURE, fallback_title=URBAN_DEVELOPMENT_LAW, fallback_mst="241111")

        response = ingest_fixture_document(db=db, query=URBAN_DEVELOPMENT_LAW, search_result=search_result, document=document)

        assert response.status == "success"
        assert response.document_id is not None
        assert response.article_count == 2
        stored_document = db.get(OfficialLawDocument, response.document_id)
        assert stored_document is not None
        assert stored_document.law_title == URBAN_DEVELOPMENT_LAW
        assert stored_document.law_id == "240001"
        assert stored_document.mst == "241111"
        assert stored_document.document_status == "normalized"
        articles = db.scalars(select(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id == stored_document.id).order_by(OfficialLawArticleRecord.sort_order)).all()
        assert len(articles) == 2
        assert articles[0].paragraphs_json
        run = db.get(OfficialLawIngestRun, response.ingest_run_id)
        assert run is not None
        assert run.status == "success"
        assert run.candidate_count == 1
        assert run.article_count == 2
        evidence = db.scalar(select(OfficialLawSourceEvidence).where(OfficialLawSourceEvidence.ingest_run_id == run.id))
        assert evidence is not None
        assert evidence.redaction_applied is True
        assert SECRET not in str(evidence.sanitized_summary_json)
    finally:
        db.close()
        _cleanup_phase24_rows()


def test_fixture_document_upsert_prevents_duplicate_document_growth():
    _cleanup_phase24_rows()
    db = SessionLocal()
    try:
        provider = MolegOpenApiLawSourceProvider(base_url="https://www.law.go.kr", api_key=SECRET)
        search_result = provider._normalize_law_search_result(SEARCH_FIXTURE, query=URBAN_DEVELOPMENT_LAW)
        document = provider._normalize_law_document(DOCUMENT_FIXTURE, fallback_title=URBAN_DEVELOPMENT_LAW, fallback_mst="241111")

        first = ingest_fixture_document(db=db, query=URBAN_DEVELOPMENT_LAW, search_result=search_result, document=document)
        second = ingest_fixture_document(db=db, query=URBAN_DEVELOPMENT_LAW, search_result=search_result, document=document)

        assert first.document_id == second.document_id
        document_count = db.scalar(select(func.count()).select_from(OfficialLawDocument).where(OfficialLawDocument.mst == "241111"))
        assert document_count == 1
    finally:
        db.close()
        _cleanup_phase24_rows()


def test_source_error_ingest_run_records_failure_without_secret():
    _cleanup_phase24_rows()
    db = SessionLocal()
    try:
        run = create_ingest_run(db=db, query=URBAN_DEVELOPMENT_LAW, source_mode="live")
        complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SOURCE_ERROR, error_reason="source_error")
        db.commit()

        stored = db.get(OfficialLawIngestRun, run.id)
        assert stored is not None
        assert stored.status == INGEST_STATUS_SOURCE_ERROR
        assert stored.error_reason == "source_error"
        assert SECRET not in str(stored.error_reason)
    finally:
        db.close()
        _cleanup_phase24_rows()


def test_moleg_diagnostic_never_exposes_secret():
    result = diagnose_moleg_connectivity()

    assert result.secret_exposed is False
    assert isinstance(result.live_configured, bool)
    assert isinstance(result.has_secret, bool)
    assert result.endpoint == "/DRF/lawSearch.do"
    assert result.reason_type in {"timeout", "connection_error", "http_error", "parse_error", "auth_error", "disabled", "unknown", "ok"}
