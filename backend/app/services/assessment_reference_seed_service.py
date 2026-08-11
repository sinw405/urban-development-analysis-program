from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Law, LawArticle, ProcedureLegalReference
from app.services.rule_loader import load_yaml_rule


@dataclass
class AssessmentSeedItemResult:
    assessment_code: str
    status: str
    law_key: str
    article_number_text: str
    reference_id: int | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class AssessmentSeedResult:
    status: str
    apply: bool
    created_count: int = 0
    existing_count: int = 0
    unresolved_count: int = 0
    items: list[AssessmentSeedItemResult] = field(default_factory=list)


def apply_assessment_reference_seeds(
    db: Session,
    *,
    apply: bool = False,
    as_of: date | None = None,
) -> AssessmentSeedResult:
    config = load_yaml_rule("assessment_legal_reference_seeds.yaml")
    seeds = config.get("references", [])
    if not isinstance(seeds, list):
        raise ValueError("assessment reference seeds must be a list")

    result = AssessmentSeedResult(status="ready", apply=apply)
    for seed in seeds:
        item = _resolve_seed(db, seed, as_of=as_of)
        result.items.append(item)
        if item.status == "unresolved":
            result.unresolved_count += 1
            continue
        if item.status == "existing":
            result.existing_count += 1
            if apply and item.reference_id is not None:
                existing = db.get(ProcedureLegalReference, item.reference_id)
                existing.reference_status = "verified"
                existing.placeholder = "VERIFIED_MOLEG_LIVE_REFERENCE"
                existing.notes_json = _provenance(seed)
            continue
        if not apply:
            continue

        law = db.scalar(select(Law).where(Law.law_key == seed["law_key"]))
        article = db.scalar(
            select(LawArticle).where(
                LawArticle.law_id == law.id,
                LawArticle.article_number_text == str(seed["article_number_text"]),
                LawArticle.article_title == seed["article_title"],
            )
        )
        reference = ProcedureLegalReference(
            step_code=seed["assessment_code"],
            law_id=law.id,
            law_article_id=article.id,
            reference_status="verified",
            placeholder="VERIFIED_MOLEG_LIVE_REFERENCE",
            notes_json=_provenance(seed),
        )
        db.add(reference)
        db.flush()
        item.status = "created"
        item.reference_id = reference.id
        result.created_count += 1

    if apply:
        db.commit()
    else:
        db.rollback()
    result.status = "completed" if result.unresolved_count == 0 else "partial"
    return result


def _resolve_seed(db: Session, seed: dict[str, Any], as_of: date | None) -> AssessmentSeedItemResult:
    code = str(seed.get("assessment_code") or "")
    law_key = str(seed.get("law_key") or "")
    article_number = str(seed.get("article_number_text") or "")
    item = AssessmentSeedItemResult(code, "ready", law_key, article_number)
    if not code or not law_key or not article_number:
        item.status = "unresolved"
        item.errors.append("invalid_seed_identity")
        return item

    law = db.scalar(select(Law).where(Law.law_key == law_key))
    if law is None:
        item.status = "unresolved"
        item.errors.append("law_not_ingested")
        return item
    article = db.scalar(
        select(LawArticle)
        .options(joinedload(LawArticle.versions))
        .where(
            LawArticle.law_id == law.id,
            LawArticle.article_number_text == article_number,
            LawArticle.article_title == seed.get("article_title"),
        )
    )
    if article is None:
        item.status = "unresolved"
        item.errors.append("article_not_ingested")
        return item
    if article.article_title != seed.get("article_title"):
        item.status = "unresolved"
        item.errors.append("article_title_mismatch")
        return item

    sources = set(seed.get("verified_version_sources", []))
    versions = [version for version in article.versions if version.article_text]
    if sources and not sources.issubset({version.source for version in versions}):
        item.status = "unresolved"
        item.errors.append("verified_source_missing")
        return item
    if as_of is not None and not any(version.effective_date and version.effective_date <= as_of for version in versions):
        item.status = "unresolved"
        item.errors.append("as_of_version_missing")
        return item

    evidence_terms = seed.get("evidence_terms", [])
    evidence_text = " ".join([article.article_title or "", *[version.article_text or "" for version in versions]])
    if not evidence_terms or not all(term in evidence_text for term in evidence_terms):
        item.status = "unresolved"
        item.errors.append("evidence_term_missing")
        return item

    existing = db.scalar(
        select(ProcedureLegalReference).where(
            ProcedureLegalReference.step_code == code,
            ProcedureLegalReference.law_article_id == article.id,
        )
    )
    if existing is not None:
        item.status = "existing"
        item.reference_id = existing.id
    return item


def _provenance(seed: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_quality": "verified",
        "reference_scope": "assessment",
        "source": seed["source"],
        "law_key": seed["law_key"],
        "article_number_text": str(seed["article_number_text"]),
        "article_title": seed["article_title"],
        "verified_version_sources": list(seed.get("verified_version_sources", [])),
        "evidence_terms": list(seed.get("evidence_terms", [])),
        "verified_at": seed["verified_at"],
        "applicability_status": "unresolved",
        "threshold_status": "placeholder",
        "requires_expert_review": True,
    }
