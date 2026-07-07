from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Law, LawArticle, LawArticleVersion
from app.services.legal_reference_service import PENDING_MOLEG_API_MAPPING, TODO_MOLEG_API_ARTICLE_CHECK
from app.services.moleg_adapter import LegalSourceAdapter, MolegLawDetailRequest, MolegLawListRequest


@dataclass(frozen=True)
class ParsedLawArticleVersion:
    effective_date: date | None = None
    article_text: str | None = None
    raw_payload_json: dict[str, Any] | None = None
    source: str = "MOLEG"
    version_status: str = PENDING_MOLEG_API_MAPPING


@dataclass(frozen=True)
class ParsedLawArticle:
    article_key: str | None = None
    article_number_text: str | None = None
    article_title: str | None = None
    mapping_status: str = TODO_MOLEG_API_ARTICLE_CHECK
    versions: list[ParsedLawArticleVersion] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedLaw:
    law_name: str
    law_key: str | None = None
    source: str = "MOLEG"
    mapping_status: str = PENDING_MOLEG_API_MAPPING
    articles: list[ParsedLawArticle] = field(default_factory=list)


@dataclass(frozen=True)
class LawIngestResult:
    law_id: int
    created_law: bool
    article_ids: list[int]
    version_ids: list[int]



def _parse_test_date(value: object) -> date | None:
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("effective_date must be an ISO date string, date, or None")

class MinimalMolegPayloadParser:
    def parse_law_detail(self, payload: dict[str, Any]) -> ParsedLaw:
        articles: list[ParsedLawArticle] = []
        for raw_article in payload.get("articles", []):
            versions = [
                ParsedLawArticleVersion(
                    effective_date=_parse_test_date(raw_version.get("effective_date")),
                    article_text=raw_version.get("article_text"),
                    raw_payload_json=raw_version,
                    source=raw_version.get("source", payload.get("source", "MOLEG")),
                    version_status=raw_version.get("version_status", PENDING_MOLEG_API_MAPPING),
                )
                for raw_version in raw_article.get("versions", [])
            ]
            articles.append(
                ParsedLawArticle(
                    article_key=raw_article.get("article_key"),
                    article_number_text=raw_article.get("article_number_text"),
                    article_title=raw_article.get("article_title"),
                    mapping_status=raw_article.get("mapping_status", TODO_MOLEG_API_ARTICLE_CHECK),
                    versions=versions,
                )
            )

        return ParsedLaw(
            law_name=payload["law_name"],
            law_key=payload.get("law_key"),
            source=payload.get("source", "MOLEG"),
            mapping_status=payload.get("mapping_status", PENDING_MOLEG_API_MAPPING),
            articles=articles,
        )


class LawIngestService:
    def __init__(self, adapter: LegalSourceAdapter | None = None, parser: MinimalMolegPayloadParser | None = None) -> None:
        self.adapter = adapter
        self.parser = parser or MinimalMolegPayloadParser()

    def build_law_list_request(self, query: str | None = None, page: int = 1, page_size: int = 20) -> MolegLawListRequest:
        return MolegLawListRequest(query=query, page=page, page_size=page_size)

    def build_law_detail_request(self, law_key: str) -> MolegLawDetailRequest:
        return MolegLawDetailRequest(law_key=law_key)

    def ingest_law_detail_payload(self, db: Session, payload: dict[str, Any]) -> LawIngestResult:
        parsed = self.parser.parse_law_detail(payload)
        return self.ingest_parsed_law(db=db, parsed=parsed)

    def ingest_parsed_law(self, db: Session, parsed: ParsedLaw) -> LawIngestResult:
        law, created_law = self._get_or_create_law(db=db, parsed=parsed)
        article_ids: list[int] = []
        version_ids: list[int] = []

        for parsed_article in parsed.articles:
            article = self._get_or_create_article(db=db, law=law, parsed=parsed_article)
            article_ids.append(article.id)
            for parsed_version in parsed_article.versions:
                version = self._get_or_create_version(db=db, article=article, parsed=parsed_version)
                version_ids.append(version.id)

        db.commit()
        return LawIngestResult(
            law_id=law.id,
            created_law=created_law,
            article_ids=article_ids,
            version_ids=version_ids,
        )

    def _get_or_create_law(self, db: Session, parsed: ParsedLaw) -> tuple[Law, bool]:
        statement = select(Law)
        if parsed.law_key:
            statement = statement.where(Law.law_key == parsed.law_key)
        else:
            statement = statement.where(Law.law_name == parsed.law_name, Law.source == parsed.source)

        law = db.scalar(statement)
        if law is not None:
            law.law_name = parsed.law_name
            law.source = parsed.source
            law.mapping_status = parsed.mapping_status
            return law, False

        law = Law(
            law_name=parsed.law_name,
            law_key=parsed.law_key,
            source=parsed.source,
            mapping_status=parsed.mapping_status,
        )
        db.add(law)
        db.flush()
        return law, True

    def _get_or_create_article(self, db: Session, law: Law, parsed: ParsedLawArticle) -> LawArticle:
        statement = select(LawArticle).where(LawArticle.law_id == law.id)
        if parsed.article_key:
            statement = statement.where(LawArticle.article_key == parsed.article_key)
        else:
            statement = statement.where(LawArticle.article_number_text == parsed.article_number_text)

        article = db.scalar(statement)
        if article is None:
            article = LawArticle(law_id=law.id)
            db.add(article)
            db.flush()

        article.article_key = parsed.article_key
        article.article_number_text = parsed.article_number_text
        article.article_title = parsed.article_title
        article.mapping_status = parsed.mapping_status
        return article

    def _get_or_create_version(
        self,
        db: Session,
        article: LawArticle,
        parsed: ParsedLawArticleVersion,
    ) -> LawArticleVersion:
        version = db.scalar(
            select(LawArticleVersion).where(
                LawArticleVersion.law_article_id == article.id,
                LawArticleVersion.effective_date == parsed.effective_date,
                LawArticleVersion.source == parsed.source,
            )
        )
        if version is None:
            version = LawArticleVersion(law_article_id=article.id)
            db.add(version)
            db.flush()

        version.effective_date = parsed.effective_date
        version.article_text = parsed.article_text
        version.raw_payload_json = parsed.raw_payload_json
        version.source = parsed.source
        version.version_status = parsed.version_status
        return version

