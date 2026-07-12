from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import OfficialLawArticleRecord, OfficialLawDocument, OfficialLawIngestRun
from app.schemas.official_law_source import OfficialLawArticleSnapshot, OfficialLawMetadata, OfficialLawSnapshotStatusResponse
from app.services.moleg_diagnostic_service import diagnose_moleg_safe
from app.services.moleg_live_client import FALLBACK_SOURCE_MODES
from app.services.official_law_seed_bootstrap_service import seed_status
from app.services.procedure_article_candidate_service import get_candidate_diagnostic_counts


class OfficialLawDbSnapshotProvider:
    source_type = "official_db"

    def __init__(self, db: Session, as_of: date | None = None) -> None:
        self.db = db
        self.as_of = as_of

    def get_article_by_law_and_article(self, law_name: str, article_number_text: str) -> OfficialLawArticleSnapshot | None:
        document = self._select_document(law_name=law_name)
        if document is None:
            return None
        normalized_article = _normalize_article_number(article_number_text)
        articles = sorted(document.articles, key=lambda item: item.sort_order)
        selected = next(
            (
                article
                for article in articles
                if _normalize_article_number(article.article_no) == normalized_article
                or normalized_article in _normalize_article_number(article.article_no)
            ),
            articles[0] if articles else None,
        )
        if selected is None:
            return None
        return _article_snapshot(document=document, article=selected, article_count=len(articles))

    def get_law_metadata(self, law_name: str) -> OfficialLawMetadata | None:
        document = self._select_document(law_name=law_name)
        if document is None:
            return None
        return OfficialLawMetadata(
            law_name=document.law_title,
            effective_date=document.enforcement_date,
            source_url=document.sanitized_source_url,
            source_type=self.source_type,
            official_law_id=document.mst or document.law_id,
            official_document_id=document.id,
            article_count=len(document.articles),
            evidence_type="official_law_documents_snapshot",
            source_hint="Loaded from official_law_documents DB snapshot.",
            source_mode_detail=_snapshot_source_mode_detail(document.source_mode),
        )

    def search_articles(self, law_name: str | None = None, keyword: str | None = None) -> list[OfficialLawArticleSnapshot]:
        if not law_name:
            return []
        document = self._select_document(law_name=law_name)
        if document is None:
            return []
        snapshots = [_article_snapshot(document=document, article=article, article_count=len(document.articles)) for article in sorted(document.articles, key=lambda item: item.sort_order)]
        if keyword:
            normalized_keyword = _normalize(keyword)
            normalized_article_keyword = _normalize_article_number(keyword)
            snapshots = [
                snapshot
                for snapshot in snapshots
                if normalized_keyword in _normalize(snapshot.article_title or "")
                or normalized_keyword in _normalize(snapshot.article_text)
                or normalized_article_keyword in _normalize_article_number(snapshot.article_number_text)
            ]
        return snapshots

    def _select_document(self, law_name: str) -> OfficialLawDocument | None:
        statement = (
            select(OfficialLawDocument)
            .options(joinedload(OfficialLawDocument.articles))
            .where(OfficialLawDocument.document_status.in_(["normalized", "partial"]))
            .order_by(
                OfficialLawDocument.is_current.desc().nullslast(),
                OfficialLawDocument.enforcement_date.desc().nullslast(),
                OfficialLawDocument.normalized_at.desc(),
                OfficialLawDocument.id.desc(),
            )
        )
        normalized_law_name = _normalize(law_name)
        candidates = self.db.scalars(statement).unique().all()
        exact = [document for document in candidates if _normalize(document.law_title) == normalized_law_name]
        if exact:
            return exact[0]
        contains = [document for document in candidates if normalized_law_name in _normalize(document.law_title)]
        return contains[0] if contains else None


def get_official_law_snapshot_status(db: Session) -> OfficialLawSnapshotStatusResponse:
    document_count = db.scalar(select(func.count()).select_from(OfficialLawDocument)) or 0
    article_count = db.scalar(select(func.count()).select_from(OfficialLawArticleRecord)) or 0
    ingest_run_count = db.scalar(select(func.count()).select_from(OfficialLawIngestRun)) or 0
    latest_run = db.scalar(select(OfficialLawIngestRun).order_by(OfficialLawIngestRun.started_at.desc(), OfficialLawIngestRun.id.desc()).limit(1))
    latest_document = db.scalar(select(OfficialLawDocument).order_by(OfficialLawDocument.normalized_at.desc(), OfficialLawDocument.id.desc()).limit(1))
    latest_manual_run = db.scalar(select(OfficialLawIngestRun).where(OfficialLawIngestRun.source_mode == "official_manual").order_by(OfficialLawIngestRun.started_at.desc(), OfficialLawIngestRun.id.desc()).limit(1))
    latest_seed_run = db.scalar(select(OfficialLawIngestRun).where(OfficialLawIngestRun.source_mode == "official_seed").order_by(OfficialLawIngestRun.started_at.desc(), OfficialLawIngestRun.id.desc()).limit(1))
    latest_seed_document = db.scalar(select(OfficialLawDocument).where(OfficialLawDocument.source_mode == "official_seed").order_by(OfficialLawDocument.normalized_at.desc(), OfficialLawDocument.id.desc()).limit(1))
    source_modes = list(db.scalars(select(OfficialLawDocument.source_mode).distinct().order_by(OfficialLawDocument.source_mode)).all())
    manual_run_count = db.scalar(select(func.count()).select_from(OfficialLawIngestRun).where(OfficialLawIngestRun.source_mode == "official_manual")) or 0
    seed_run_count = db.scalar(select(func.count()).select_from(OfficialLawIngestRun).where(OfficialLawIngestRun.source_mode == "official_seed")) or 0
    documents = db.scalars(select(OfficialLawDocument)).all()
    candidate_counts = get_candidate_diagnostic_counts(db)
    moleg_diagnostic = _safe_moleg_snapshot_diagnostic()
    seed_diagnostic = _safe_seed_snapshot_diagnostic()
    return OfficialLawSnapshotStatusResponse(
        document_count=document_count,
        article_count=article_count,
        ingest_run_count=ingest_run_count,
        latest_ingest_status=None if latest_run is None else latest_run.status,
        source_provider=None if latest_document is None else latest_document.source_provider,
        last_normalized_at=None if latest_document is None else latest_document.normalized_at,
        has_current_documents=any(document.is_current is True for document in documents),
        source_modes=source_modes,
        manual_import_count=manual_run_count,
        latest_manual_import_status=None if latest_manual_run is None else latest_manual_run.status,
        latest_source_provider=None if latest_document is None else latest_document.source_provider,
        latest_mode=None if latest_document is None else latest_document.source_mode,
        latest_error_reason=None if latest_run is None else latest_run.error_reason,
        seed_import_count=seed_run_count,
        latest_seed_import_status=None if latest_seed_run is None else latest_seed_run.status,
        latest_seed_law_title=None if latest_seed_document is None else latest_seed_document.law_title,
        latest_seed_law_id=None if latest_seed_document is None else latest_seed_document.law_id,
        latest_seed_mst=None if latest_seed_document is None else latest_seed_document.mst,
        latest_seed_enforcement_date=None if latest_seed_document is None else latest_seed_document.enforcement_date,
        has_urban_development_law=_has_document_title(documents, "\ub3c4\uc2dc\uac1c\ubc1c\ubc95"),
        has_urban_development_enforcement_decree=_has_document_title(documents, "\ub3c4\uc2dc\uac1c\ubc1c\ubc95 \uc2dc\ud589\ub839"),
        has_urban_development_enforcement_rule=_has_document_title(documents, "\ub3c4\uc2dc\uac1c\ubc1c\ubc95 \uc2dc\ud589\uaddc\uce59"),
        **candidate_counts,
        **moleg_diagnostic,
        **seed_diagnostic,
    )


def _article_snapshot(document: OfficialLawDocument, article: OfficialLawArticleRecord, article_count: int) -> OfficialLawArticleSnapshot:
    return OfficialLawArticleSnapshot(
        law_name=document.law_title,
        article_number_text=article.article_no,
        article_title=article.article_title,
        article_text=article.article_text,
        effective_date=document.enforcement_date,
        source_url=document.sanitized_source_url,
        source_type="official_db",
        official_law_id=document.mst or document.law_id,
        official_document_id=document.id,
        article_count=article_count,
        evidence_type="official_law_documents_snapshot",
        source_hint="Loaded from official_law_documents DB snapshot.",
        source_mode_detail=_snapshot_source_mode_detail(document.source_mode),
    )


def _snapshot_source_mode_detail(source_mode: str | None) -> str:
    if source_mode == "official_manual":
        return "official_manual_db"
    if source_mode == "official_seed":
        return "official_seed_db"
    return "official_db"


def _has_document_title(documents: list[OfficialLawDocument], title: str) -> bool:
    normalized_title = _normalize(title)
    return any(_normalize(document.law_title) == normalized_title or _normalize(document.law_short_title or "") == normalized_title for document in documents)


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _normalize_article_number(value: str) -> str:
    return _normalize(value).replace(" ", "")


def _safe_moleg_snapshot_diagnostic() -> dict[str, object]:
    try:
        diagnostic = diagnose_moleg_safe()
        return {
            "moleg_live_enabled": diagnostic.live_enabled,
            "moleg_configured": diagnostic.configured,
            "moleg_transport_ok": diagnostic.transport_ok,
            "moleg_reason_type": diagnostic.reason_type,
            "moleg_final_reason_type": diagnostic.final_reason_type or diagnostic.reason_type,
            "moleg_reason_message_ko": diagnostic.reason_message_ko or diagnostic.reason_message,
            "moleg_search_ok": diagnostic.search_ok,
            "moleg_detail_ok": diagnostic.detail_ok,
            "moleg_parse_ok": diagnostic.parse_ok,
            "moleg_browser_success_metadata_present": diagnostic.browser_success_metadata_present,
            "moleg_selected_endpoint": diagnostic.selected_endpoint,
            "moleg_ready_for_live_ingest": diagnostic.ready_for_live_ingest,
            "moleg_suggested_fix": diagnostic.suggested_fix or diagnostic.next_action,
            "moleg_last_checked_at": diagnostic.checked_at,
            "moleg_secret_exposed": diagnostic.secret_exposed,
            "moleg_raw_payload_stored": diagnostic.raw_payload_stored,
            "fallback_available": diagnostic.fallback_available,
            "fallback_source_modes": diagnostic.fallback_source_modes,
        }
    except Exception:
        return {
            "moleg_live_enabled": False,
            "moleg_configured": False,
            "moleg_transport_ok": False,
            "moleg_reason_type": "unknown_connection_error",
            "moleg_final_reason_type": "unknown_connection_error",
            "moleg_reason_message_ko": "법제처 API 연결 오류 원인을 추가 확인해야 합니다.",
            "moleg_search_ok": False,
            "moleg_detail_ok": False,
            "moleg_parse_ok": False,
            "moleg_browser_success_metadata_present": False,
            "moleg_selected_endpoint": None,
            "moleg_ready_for_live_ingest": False,
            "moleg_suggested_fix": None,
            "moleg_last_checked_at": None,
            "moleg_secret_exposed": False,
            "moleg_raw_payload_stored": False,
            "fallback_available": True,
            "fallback_source_modes": FALLBACK_SOURCE_MODES,
        }


def _safe_seed_snapshot_diagnostic() -> dict[str, object]:
    try:
        status = seed_status()
        return {
            "official_seed_files_count": status["total_files"],
            "official_seed_articles_count": status["total_articles"],
            "official_seed_confirmed_count": status["confirmed_articles"],
            "official_seed_unconfirmed_count": status["unconfirmed_articles"],
            "official_seed_ready_for_manual_authoring": status["ready_for_manual_authoring"],
            "official_seed_authoring_checklist_exists": status["authoring_checklist_exists"],
            "official_seed_review_manifest_template_exists": status["review_manifest_template_exists"],
            "official_seed_dry_run_supported": status["dry_run_supported"],
            "official_seed_fixture_validation_supported": status["fixture_validation_supported"],
            "official_seed_empty_files_count": status["empty_files"],
            "official_seed_validation_status": status["validation_status"],
            "official_seed_source_material_directory_exists": status["source_material_directory_exists"],
            "official_seed_source_intake_status": status["source_intake_status"],
            "official_seed_source_intake_rows": status["source_intake_rows"],
            "official_seed_ready_for_seed_generation": status["ready_for_seed_generation"],
            "official_seed_batch1_policy_exists": status["batch1_policy_exists"],
            "secret_exposed": status["secret_exposed"],
        }
    except Exception:
        return {
            "official_seed_files_count": 0,
            "official_seed_articles_count": 0,
            "official_seed_confirmed_count": 0,
            "official_seed_unconfirmed_count": 0,
            "official_seed_ready_for_manual_authoring": False,
            "official_seed_authoring_checklist_exists": False,
            "official_seed_review_manifest_template_exists": False,
            "official_seed_dry_run_supported": True,
            "official_seed_fixture_validation_supported": True,
            "official_seed_empty_files_count": 0,
            "official_seed_validation_status": "unknown",
            "official_seed_source_material_directory_exists": False,
            "official_seed_source_intake_status": "unknown",
            "official_seed_source_intake_rows": 0,
            "official_seed_ready_for_seed_generation": False,
            "official_seed_batch1_policy_exists": False,
            "secret_exposed": False,
        }
