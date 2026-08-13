from __future__ import annotations

from datetime import date
import hashlib
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Law, LawArticle, LawAttachedTableEvidence, OfficialLawDocument
from app.schemas.legal_retrieval import LegalRetrievalResult
from app.services.law_version_service import get_current_article_version

STRATEGY = "deterministic_lexical_v1"


def normalize_search_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-zA-Z가-힣]+", " ", value or "").lower()).strip()


def _query_terms(query: str) -> list[str]:
    normalized = normalize_search_text(query)
    words = [word for word in normalized.split() if word]
    return list(dict.fromkeys(([normalized] if normalized else []) + words))


def _hash(source_identifier: str, text: str) -> str:
    return hashlib.sha256(f"{source_identifier}\n{text}".encode("utf-8")).hexdigest()


def _mst(source: str | None) -> str | None:
    return source.split(":", 1)[1] if source and source.startswith("MOLEG_LIVE:") else None


def _official_source_url(db: Session, law: Law, mst: str | None) -> str | None:
    if not mst:
        return None
    for document in db.scalars(select(OfficialLawDocument).where(OfficialLawDocument.mst == mst)).all():
        if document.law_id not in {None, law.law_key} and document.law_title != law.law_name:
            continue
        value = document.sanitized_source_url.strip()
        if value.startswith('https://www.law.go.kr/') or value.startswith('https://law.go.kr/'):
            return value
    return None


def _score(query_terms: list[str], law_name: str, title: str, text: str) -> float:
    law = normalize_search_text(law_name); heading = normalize_search_text(title); body = normalize_search_text(text)
    score = 0.0
    for term in query_terms:
        if not term:
            continue
        score += law.count(term) * 4.0 + heading.count(term) * 6.0 + body.count(term) * 1.0
        for word in term.split():
            if len(word) >= 2:
                score += law.count(word) * 2.0 + heading.count(word) * 3.0 + body.count(word) * 0.5
    return round(score, 6)


def _excerpt(text: str, terms: list[str], limit: int = 500) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    lowered = compact.lower(); positions = [lowered.find(term) for term in terms if term and lowered.find(term) >= 0]
    start = max(0, min(positions) - 100) if positions else 0
    return compact[start:start + limit]


def build_legal_corpus(db: Session, as_of: date, source_types: set[str] | None = None) -> list[LegalRetrievalResult]:
    allowed = source_types or {"article", "attached_table"}
    results: list[LegalRetrievalResult] = []
    if "article" in allowed:
        for article, law in db.execute(select(LawArticle, Law).join(Law)).all():
            version = get_current_article_version(db, article.id, as_of)
            if version is None or not version.article_text:
                continue
            source_id = f"article:{article.id}:version:{version.id}"
            citation = f"law:{law.law_key or law.id}:article:{article.article_key or article.id}:asof:{as_of.isoformat()}"
            text = version.article_text
            results.append(LegalRetrievalResult(
                source_type="article", law_identifier=law.law_key or str(law.id), law_name=law.law_name,
                source_identifier=source_id, title=article.article_title or article.article_number_text or "Untitled article",
                text=text, text_excerpt=text[:500], effective_date=version.effective_date, version_status="current",
                mst=_mst(version.source), provenance={"source": version.source, "mapping_status": article.mapping_status, "official_source_url": _official_source_url(db, law, _mst(version.source))},
                citation_id=citation, content_hash=_hash(source_id, text), relevance_score=0,
            ))
    if "attached_table" in allowed:
        rows = db.execute(
            select(LawAttachedTableEvidence, Law).join(Law)
            .where(LawAttachedTableEvidence.effective_date.is_not(None), LawAttachedTableEvidence.effective_date <= as_of)
            .order_by(LawAttachedTableEvidence.effective_date.desc(), LawAttachedTableEvidence.id.desc())
        ).all()
        selected: dict[tuple[int, str], tuple[LawAttachedTableEvidence, Law]] = {}
        for evidence, law in rows:
            selected.setdefault((law.id, evidence.table_key), (evidence, law))
        for evidence, law in selected.values():
            source_id = f"attached-table:{evidence.id}"
            citation = f"law:{law.law_key or law.id}:table:{evidence.table_number}:mst:{evidence.mst}"
            results.append(LegalRetrievalResult(
                source_type="attached_table", law_identifier=law.law_key or str(law.id), law_name=law.law_name,
                source_identifier=source_id, title=evidence.table_title, text=evidence.normalized_text,
                text_excerpt=evidence.normalized_text[:500], effective_date=evidence.effective_date,
                version_status="current", mst=evidence.mst, provenance={**evidence.provenance_json, "official_source_url": _official_source_url(db, law, evidence.mst)},
                citation_id=citation, content_hash=_hash(source_id, evidence.normalized_text), relevance_score=0,
            ))
    return results


def retrieve_legal_evidence(db: Session, query: str, as_of: date, top_k: int = 5, source_types: Iterable[str] | None = None) -> list[LegalRetrievalResult]:
    terms = _query_terms(query)
    corpus = build_legal_corpus(db, as_of, None if source_types is None else set(source_types))
    ranked: list[LegalRetrievalResult] = []
    seen: set[str] = set()
    for document in corpus:
        score = _score(terms, document.law_name, document.title, document.text)
        if score <= 0 or document.citation_id in seen:
            continue
        seen.add(document.citation_id)
        document.relevance_score = score
        document.text_excerpt = _excerpt(document.text, terms)
        ranked.append(document)
    ranked.sort(key=lambda item: (-item.relevance_score, item.citation_id))
    return ranked[:top_k]
