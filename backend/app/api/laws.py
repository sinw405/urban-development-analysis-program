from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Law, LawArticle

router = APIRouter(tags=["laws"])


@router.get("/laws")
def list_laws(db: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    laws = db.scalars(select(Law).order_by(Law.id)).all()
    return {
        "items": [
            {
                "id": law.id,
                "law_name": law.law_name,
                "law_key": law.law_key,
                "source": law.source,
                "mapping_status": law.mapping_status,
            }
            for law in laws
        ]
    }


@router.get("/laws/{law_id}/articles")
def list_law_articles(law_id: int, db: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    law = db.get(Law, law_id)
    if law is None:
        raise HTTPException(status_code=404, detail="Law not found")

    articles = db.scalars(select(LawArticle).where(LawArticle.law_id == law_id).order_by(LawArticle.id)).all()
    return {
        "items": [
            {
                "id": article.id,
                "law_id": article.law_id,
                "article_key": article.article_key,
                "article_number_text": article.article_number_text,
                "article_title": article.article_title,
                "mapping_status": article.mapping_status,
            }
            for article in articles
        ]
    }
