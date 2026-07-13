from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Law, LawArticle, LawArticleVersion
from app.schemas.laws import (
    LawArticleListResponse,
    LawArticleSummary,
    LawArticleVersionListResponse,
    LawArticleVersionSummary,
    LawListResponse,
    LawSummary,
)
from app.services.law_version_service import VERSION_STATUS_CURRENT, get_article_versions

router = APIRouter(tags=["laws"])



def _coverage_metadata(db: Session, law_id: int, as_of: date | None, total_articles: int, current_version_count: int) -> dict:
    versions = list(
        db.scalars(
            select(LawArticleVersion)
            .join(LawArticle)
            .where(LawArticle.law_id == law_id, LawArticleVersion.effective_date.is_not(None))
            .order_by(LawArticleVersion.effective_date.asc(), LawArticleVersion.id.asc())
        ).all()
    )
    dates = sorted({version.effective_date for version in versions if version.effective_date is not None})
    available_from = dates[0] if dates else None
    available_to = dates[-1] if dates else None
    selected_versions = [version for version in versions if as_of is not None and version.effective_date is not None and version.effective_date <= as_of]
    selected_effective_date = max((version.effective_date for version in selected_versions), default=None)
    selected_sources = sorted({version.source for version in selected_versions if version.effective_date == selected_effective_date}) if selected_effective_date else []
    selected_mst = None
    if len(selected_sources) == 1 and selected_sources[0].startswith("MOLEG_LIVE:"):
        selected_mst = selected_sources[0].split(":", 1)[1]
    if not dates:
        coverage_status = "no_versions"
    elif as_of is None:
        coverage_status = "available"
    elif as_of < available_from:
        coverage_status = "before_available_history"
    elif current_version_count == 0:
        coverage_status = "no_applicable_version"
    else:
        coverage_status = "covered"
    return {
        "coverage_status": coverage_status,
        "available_from": available_from,
        "available_to": available_to,
        "total_articles": total_articles,
        "applicable_articles": current_version_count,
        "current_version_count": current_version_count,
        "selected_mst": selected_mst,
        "selected_effective_date": selected_effective_date,
        "version_status": "current" if current_version_count else None,
        "history_complete": len(dates) > 1,
    }

def _version_summary(item) -> LawArticleVersionSummary:
    version = item.version
    return LawArticleVersionSummary(
        id=version.id,
        law_article_id=version.law_article_id,
        effective_date=version.effective_date,
        article_text=version.article_text,
        raw_payload_json=version.raw_payload_json,
        source=version.source,
        version_status=version.version_status,
        temporal_status=item.temporal_status,
    )


def _article_summary(db: Session, article: LawArticle, as_of: date | None) -> LawArticleSummary:
    current_version = None
    if as_of is not None:
        for item in get_article_versions(db=db, article_id=article.id, as_of=as_of):
            if item.temporal_status == VERSION_STATUS_CURRENT:
                current_version = _version_summary(item)
                break

    return LawArticleSummary(
        id=article.id,
        law_id=article.law_id,
        article_key=article.article_key,
        article_number_text=article.article_number_text,
        article_title=article.article_title,
        mapping_status=article.mapping_status,
        current_version=current_version,
    )


@router.get("/laws", response_model=LawListResponse)
def list_laws(db: Session = Depends(get_db)) -> LawListResponse:
    laws = db.scalars(select(Law).order_by(Law.id)).all()
    return LawListResponse(
        items=[
            LawSummary(
                id=law.id,
                law_name=law.law_name,
                law_key=law.law_key,
                source=law.source,
                mapping_status=law.mapping_status,
            )
            for law in laws
        ]
    )


@router.get("/laws/{law_id}/articles", response_model=LawArticleListResponse)
def list_law_articles(
    law_id: int,
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> LawArticleListResponse:
    law = db.get(Law, law_id)
    if law is None:
        raise HTTPException(status_code=404, detail="Law not found")

    articles = db.scalars(select(LawArticle).where(LawArticle.law_id == law_id).order_by(LawArticle.id)).all()
    items = [_article_summary(db=db, article=article, as_of=as_of) for article in articles]
    coverage = _coverage_metadata(db=db, law_id=law_id, as_of=as_of, total_articles=len(articles), current_version_count=sum(1 for item in items if item.current_version is not None))
    return LawArticleListResponse(
        as_of=as_of,
        requested_as_of=as_of,
        items=items,
        **coverage,
    )


@router.get("/laws/{law_id}/articles/{article_id}/versions", response_model=LawArticleVersionListResponse)
def list_law_article_versions(
    law_id: int,
    article_id: int,
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> LawArticleVersionListResponse:
    article = db.get(LawArticle, article_id)
    if article is None or article.law_id != law_id:
        raise HTTPException(status_code=404, detail="Law article not found")

    version_items = [_version_summary(item) for item in get_article_versions(db=db, article_id=article_id, as_of=as_of)]
    current_version = next((item for item in version_items if item.temporal_status == VERSION_STATUS_CURRENT), None)
    return LawArticleVersionListResponse(
        law_id=law_id,
        article_id=article_id,
        as_of=as_of,
        items=version_items,
        current_version=current_version,
    )
