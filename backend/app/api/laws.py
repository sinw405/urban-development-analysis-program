from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Law, LawArticle
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
    return LawArticleListResponse(
        as_of=as_of,
        items=[_article_summary(db=db, article=article, as_of=as_of) for article in articles],
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
