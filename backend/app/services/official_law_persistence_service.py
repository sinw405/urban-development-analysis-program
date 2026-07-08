from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    OfficialLawArticleRecord,
    OfficialLawDocument as OfficialLawDocumentModel,
    OfficialLawIngestRun,
    OfficialLawSourceEvidence,
)
from app.schemas.official_law_source import (
    OfficialLawCandidate,
    OfficialLawDocument,
    OfficialLawIngestPreviewResponse,
    OfficialLawSearchResult,
)
from app.services.official_law_source import LawSourceProviderError, LawSourceProviderUnavailable, MolegOpenApiLawSourceProvider, redact_secret_values

INGEST_STATUS_STARTED = "started"
INGEST_STATUS_SUCCESS = "success"
INGEST_STATUS_SOURCE_ERROR = "source_error"
INGEST_STATUS_SOURCE_UNAVAILABLE = "source_unavailable"
DOCUMENT_STATUS_NORMALIZED = "normalized"
DOCUMENT_STATUS_PARTIAL = "partial"


def create_ingest_run(db: Session, query: str | None, source_mode: str, run_type: str = "official_law_document") -> OfficialLawIngestRun:
    run = OfficialLawIngestRun(run_type=run_type, source_mode=source_mode, query=query, status=INGEST_STATUS_STARTED)
    db.add(run)
    db.flush()
    return run


def persist_official_law_document(
    db: Session,
    document: OfficialLawDocument,
    selected_candidate: OfficialLawCandidate | None,
    source_provider: str = "moleg_open_api",
    source_mode: str = "fixture",
) -> OfficialLawDocumentModel:
    existing = _find_existing_document(db=db, document=document, selected_candidate=selected_candidate, source_provider=source_provider)
    if existing is None:
        existing = OfficialLawDocumentModel(
            source_provider=source_provider,
            source_mode=source_mode,
            law_title=document.title,
            law_short_title=None if selected_candidate is None else selected_candidate.short_title,
            law_id=document.law_id or (None if selected_candidate is None else selected_candidate.law_id),
            mst=document.mst or (None if selected_candidate is None else selected_candidate.mst),
            promulgation_date=None if selected_candidate is None else selected_candidate.promulgation_date,
            enforcement_date=document.enforcement_date or (None if selected_candidate is None else selected_candidate.enforcement_date),
            is_current=None if selected_candidate is None else selected_candidate.is_current,
            document_status=DOCUMENT_STATUS_NORMALIZED if document.articles else DOCUMENT_STATUS_PARTIAL,
            normalized_at=document.normalized_at,
            provider_reason=document.provider_reason,
            sanitized_source_url=document.sanitized_source_url,
        )
        db.add(existing)
        db.flush()
    else:
        existing.source_mode = source_mode
        existing.law_title = document.title
        existing.law_short_title = None if selected_candidate is None else selected_candidate.short_title
        existing.law_id = document.law_id or (None if selected_candidate is None else selected_candidate.law_id)
        existing.mst = document.mst or (None if selected_candidate is None else selected_candidate.mst)
        existing.promulgation_date = None if selected_candidate is None else selected_candidate.promulgation_date
        existing.enforcement_date = document.enforcement_date or (None if selected_candidate is None else selected_candidate.enforcement_date)
        existing.is_current = None if selected_candidate is None else selected_candidate.is_current
        existing.document_status = DOCUMENT_STATUS_NORMALIZED if document.articles else DOCUMENT_STATUS_PARTIAL
        existing.normalized_at = document.normalized_at
        existing.provider_reason = document.provider_reason
        existing.sanitized_source_url = document.sanitized_source_url
        db.flush()

    db.execute(delete(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id == existing.id))
    for index, article in enumerate(document.articles, start=1):
        db.add(
            OfficialLawArticleRecord(
                document_id=existing.id,
                article_no=article.article_no,
                article_title=article.article_title,
                article_text=article.article_text,
                paragraphs_json=article.paragraphs,
                source_anchor=article.source_anchor,
                source_hint=article.source_hint,
                sort_order=index,
            )
        )
    db.flush()
    return existing


def complete_ingest_run(
    db: Session,
    run: OfficialLawIngestRun,
    status: str,
    search_result: OfficialLawSearchResult | None = None,
    document: OfficialLawDocument | None = None,
    error_reason: str | None = None,
) -> OfficialLawIngestRun:
    selected = None if search_result is None else search_result.selected_candidate
    run.status = status
    run.selected_law_title = None if selected is None else selected.title
    run.selected_law_id = None if selected is None else selected.law_id
    run.selected_mst = None if selected is None else selected.mst
    run.candidate_count = 0 if search_result is None else len(search_result.candidates)
    run.article_count = 0 if document is None else len(document.articles)
    run.error_reason = error_reason
    run.finished_at = datetime.now(UTC)
    db.flush()
    return run


def add_source_evidence(
    db: Session,
    run: OfficialLawIngestRun,
    evidence_type: str,
    summary: dict[str, Any] | None,
    raw_available: bool,
) -> OfficialLawSourceEvidence:
    evidence = OfficialLawSourceEvidence(
        ingest_run_id=run.id,
        evidence_type=evidence_type,
        sanitized_summary_json=redact_secret_values(summary or {}),
        raw_available=raw_available,
        redaction_applied=True,
    )
    db.add(evidence)
    db.flush()
    return evidence


def ingest_fixture_document(
    db: Session,
    query: str,
    search_result: OfficialLawSearchResult,
    document: OfficialLawDocument,
    source_mode: str = "fixture",
) -> OfficialLawIngestPreviewResponse:
    run = create_ingest_run(db=db, query=query, source_mode=source_mode)
    selected = search_result.selected_candidate
    stored_document = persist_official_law_document(db=db, document=document, selected_candidate=selected, source_mode=source_mode)
    complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SUCCESS, search_result=search_result, document=document)
    add_source_evidence(
        db=db,
        run=run,
        evidence_type="normalized_document_summary",
        summary={
            "selected_title": None if selected is None else selected.title,
            "selected_mst": None if selected is None else selected.mst,
            "article_count": len(document.articles),
            "sanitized_source_url": document.sanitized_source_url,
        },
        raw_available=document.raw_available,
    )
    db.commit()
    return OfficialLawIngestPreviewResponse(
        status=INGEST_STATUS_SUCCESS,
        source_mode="mock" if source_mode == "mock" else "live",
        selected_candidate=selected,
        document_id=stored_document.id,
        ingest_run_id=run.id,
        article_count=len(document.articles),
        provider_reason=document.provider_reason,
        secret_exposed=False,
    )


def ingest_live_document_preview(db: Session, query: str) -> OfficialLawIngestPreviewResponse:
    run = create_ingest_run(db=db, query=query, source_mode="live")
    provider = MolegOpenApiLawSourceProvider()
    try:
        search_result = provider.search_laws(query)
        selected = search_result.selected_candidate
        if selected is None or not selected.mst:
            complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SOURCE_UNAVAILABLE, search_result=search_result, error_reason="No selected candidate MST.")
            db.commit()
            return OfficialLawIngestPreviewResponse(status=INGEST_STATUS_SOURCE_UNAVAILABLE, source_mode="live", selected_candidate=selected, document_id=None, ingest_run_id=run.id, article_count=0, provider_reason="No selected candidate MST.", secret_exposed=False)
        document = provider.get_law_document(selected.mst, fallback_title=selected.title)
        stored_document = persist_official_law_document(db=db, document=document, selected_candidate=selected, source_mode="live")
        complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SUCCESS, search_result=search_result, document=document)
        add_source_evidence(db=db, run=run, evidence_type="live_normalized_document_summary", summary={"selected_title": selected.title, "selected_mst": selected.mst, "article_count": len(document.articles), "sanitized_source_url": document.sanitized_source_url}, raw_available=document.raw_available)
        db.commit()
        return OfficialLawIngestPreviewResponse(status=INGEST_STATUS_SUCCESS, source_mode="live", selected_candidate=selected, document_id=stored_document.id, ingest_run_id=run.id, article_count=len(document.articles), provider_reason=document.provider_reason, secret_exposed=False)
    except LawSourceProviderUnavailable:
        complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SOURCE_UNAVAILABLE, error_reason="source_unavailable")
        db.commit()
        return OfficialLawIngestPreviewResponse(status=INGEST_STATUS_SOURCE_UNAVAILABLE, source_mode="live", selected_candidate=None, document_id=None, ingest_run_id=run.id, article_count=0, provider_reason="source_unavailable", secret_exposed=False)
    except LawSourceProviderError:
        complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SOURCE_ERROR, error_reason="source_error")
        db.commit()
        return OfficialLawIngestPreviewResponse(status=INGEST_STATUS_SOURCE_ERROR, source_mode="live", selected_candidate=None, document_id=None, ingest_run_id=run.id, article_count=0, provider_reason="source_error", secret_exposed=False)


def _find_existing_document(
    db: Session,
    document: OfficialLawDocument,
    selected_candidate: OfficialLawCandidate | None,
    source_provider: str,
) -> OfficialLawDocumentModel | None:
    law_id = document.law_id or (None if selected_candidate is None else selected_candidate.law_id)
    mst = document.mst or (None if selected_candidate is None else selected_candidate.mst)
    statement = select(OfficialLawDocumentModel).where(
        OfficialLawDocumentModel.source_provider == source_provider,
        OfficialLawDocumentModel.law_id == law_id,
        OfficialLawDocumentModel.mst == mst,
        OfficialLawDocumentModel.enforcement_date == document.enforcement_date,
    )
    return db.scalar(statement)
