from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import OfficialLawArticleRecord, OfficialLawDocument, OfficialLawIngestRun
from app.schemas.official_law_source import OfficialLawArticleSnapshot, OfficialLawMetadata, OfficialLawSnapshotStatusResponse
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
        has_urban_development_law=_has_document_title(documents, "도시개발법"),
        has_urban_development_enforcement_decree=_has_document_title(documents, "도시개발법 시행령"),
        has_urban_development_enforcement_rule=_has_document_title(documents, "도시개발법 시행규칙"),
        **candidate_counts,
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
