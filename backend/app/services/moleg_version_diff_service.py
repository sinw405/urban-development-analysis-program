from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OfficialLawArticleRecord, OfficialLawDocument


@dataclass(frozen=True)
class ArticleDiffItem:
    article_no: str
    article_title: str | None = None
    from_article_id: int | None = None
    to_article_id: int | None = None


@dataclass
class MolegVersionDiffResult:
    law_name: str
    law_id: str | None
    from_mst: str
    to_mst: str
    from_effective_date: str | None
    to_effective_date: str | None
    added: list[ArticleDiffItem] = field(default_factory=list)
    removed: list[ArticleDiffItem] = field(default_factory=list)
    changed: list[ArticleDiffItem] = field(default_factory=list)
    unchanged: list[ArticleDiffItem] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source_provenance: dict[str, Any] = field(default_factory=dict)
    raw_payload_stored: bool = False
    secret_exposed: bool = False
    status: str = "ok"
    reason_type: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "law_name": self.law_name,
            "law_id": self.law_id,
            "from_mst": self.from_mst,
            "to_mst": self.to_mst,
            "from_effective_date": self.from_effective_date,
            "to_effective_date": self.to_effective_date,
            "added_count": len(self.added),
            "removed_count": len(self.removed),
            "changed_count": len(self.changed),
            "unchanged_count": len(self.unchanged),
            "added": [item.__dict__ for item in self.added],
            "removed": [item.__dict__ for item in self.removed],
            "changed_article_identifiers": [item.__dict__ for item in self.changed],
            "generated_at": self.generated_at,
            "source_provenance": self.source_provenance,
            "raw_payload_stored": self.raw_payload_stored,
            "secret_exposed": self.secret_exposed,
            "status": self.status,
            "reason_type": self.reason_type,
        }


def diff_moleg_versions(db: Session, law_name: str, from_mst: str, to_mst: str) -> MolegVersionDiffResult:
    from_doc = _find_document(db, law_name, from_mst)
    to_doc = _find_document(db, law_name, to_mst)
    if from_doc is None or to_doc is None:
        return MolegVersionDiffResult(
            law_name=law_name,
            law_id=None,
            from_mst=from_mst,
            to_mst=to_mst,
            from_effective_date=None if from_doc is None else str(from_doc.enforcement_date),
            to_effective_date=None if to_doc is None else str(to_doc.enforcement_date),
            status="missing_version",
            reason_type="version_not_available",
        )
    from_articles = _articles(db, from_doc.id)
    to_articles = _articles(db, to_doc.id)
    from_duplicates = _duplicate_article_numbers(from_articles)
    to_duplicates = _duplicate_article_numbers(to_articles)
    from_items = {_article_identity(item, from_duplicates): item for item in from_articles}
    to_items = {_article_identity(item, to_duplicates): item for item in to_articles}
    result = MolegVersionDiffResult(
        law_name=to_doc.law_title,
        law_id=to_doc.law_id or from_doc.law_id,
        from_mst=from_mst,
        to_mst=to_mst,
        from_effective_date=None if from_doc.enforcement_date is None else str(from_doc.enforcement_date),
        to_effective_date=None if to_doc.enforcement_date is None else str(to_doc.enforcement_date),
        source_provenance={
            "source_provider": to_doc.source_provider,
            "source_mode": to_doc.source_mode,
            "from_document_id": from_doc.id,
            "to_document_id": to_doc.id,
        },
    )
    for key in sorted(set(from_items) | set(to_items)):
        before = from_items.get(key)
        after = to_items.get(key)
        if before is None and after is not None:
            result.added.append(_item(after, to_article_id=after.id))
        elif before is not None and after is None:
            result.removed.append(_item(before, from_article_id=before.id))
        elif before is not None and after is not None:
            item = _item(after, from_article_id=before.id, to_article_id=after.id)
            if _content_hash(before) == _content_hash(after):
                result.unchanged.append(item)
            else:
                result.changed.append(item)
    return result


def _find_document(db: Session, law_name: str, mst: str) -> OfficialLawDocument | None:
    return db.scalar(
        select(OfficialLawDocument).where(
            OfficialLawDocument.source_provider == "moleg_open_api",
            OfficialLawDocument.source_mode == "live",
            OfficialLawDocument.law_title == law_name,
            OfficialLawDocument.mst == mst,
        )
    )


def _articles(db: Session, document_id: int) -> list[OfficialLawArticleRecord]:
    return list(db.scalars(select(OfficialLawArticleRecord).where(OfficialLawArticleRecord.document_id == document_id).order_by(OfficialLawArticleRecord.sort_order, OfficialLawArticleRecord.id)).all())


def _duplicate_article_numbers(articles: list[OfficialLawArticleRecord]) -> set[str]:
    counts: dict[str, int] = {}
    for article in articles:
        counts[article.article_no] = counts.get(article.article_no, 0) + 1
    return {article_no for article_no, count in counts.items() if count > 1}


def _article_identity(article: OfficialLawArticleRecord, duplicate_numbers: set[str]) -> str:
    if article.source_anchor:
        return f"{article.article_no}|{article.source_anchor}"
    if article.article_no in duplicate_numbers:
        return f"{article.article_no}|{article.sort_order}"
    return article.article_no


def _content_hash(article: OfficialLawArticleRecord) -> str:
    normalized = "\n".join([_normalize(article.article_title or ""), _normalize(article.article_text or "")])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _item(article: OfficialLawArticleRecord, from_article_id: int | None = None, to_article_id: int | None = None) -> ArticleDiffItem:
    return ArticleDiffItem(article_no=article.article_no, article_title=article.article_title, from_article_id=from_article_id, to_article_id=to_article_id)