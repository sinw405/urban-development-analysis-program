from datetime import date
from typing import Any

from pydantic import BaseModel


class LawSummary(BaseModel):
    id: int
    law_name: str
    law_key: str | None
    source: str
    mapping_status: str


class LawListResponse(BaseModel):
    items: list[LawSummary]


class LawArticleVersionSummary(BaseModel):
    id: int
    law_article_id: int
    effective_date: date | None
    article_text: str | None
    source: str
    version_status: str
    temporal_status: str | None = None
    raw_payload_json: dict[str, Any] | None = None


class LawArticleSummary(BaseModel):
    id: int
    law_id: int
    article_key: str | None
    article_number_text: str | None
    article_title: str | None
    mapping_status: str
    current_version: LawArticleVersionSummary | None = None


class LawArticleListResponse(BaseModel):
    items: list[LawArticleSummary]
    as_of: date | None = None


class LawArticleVersionListResponse(BaseModel):
    law_id: int
    article_id: int
    as_of: date | None = None
    items: list[LawArticleVersionSummary]
    current_version: LawArticleVersionSummary | None = None
