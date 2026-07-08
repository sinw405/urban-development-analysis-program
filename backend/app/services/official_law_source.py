from __future__ import annotations

from datetime import UTC, date, datetime
from math import ceil
from typing import Any, Protocol
from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings
from app.schemas.official_law_source import (
    OfficialLawArticle,
    OfficialLawArticleSnapshot,
    OfficialLawCandidate,
    OfficialLawDocument,
    OfficialLawMetadata,
    OfficialLawPagination,
    OfficialLawSearchResult,
)

MOLEG_LAW_SEARCH_PATH = "/DRF/lawSearch.do"
MOLEG_LAW_SERVICE_PATH = "/DRF/lawService.do"
MOLEG_LAW_TARGET = "law"
MOLEG_JSON_TYPE = "JSON"
MOLEG_XML_TYPE = "XML"
SECRET_REDACTION = "[REDACTED]"
SECRET_KEYS = {"OC", "oc", "api_key", "apikey", "MOLEG_API_KEY", "MOLEG_OC"}

K_LAW_NAME_HANGUL = "\ubc95\ub839\uba85\ud55c\uae00"
K_LAW_NAME = "\ubc95\ub839\uba85"
K_LAW_SHORT_NAME = "\ubc95\ub839\uc57d\uce6d\uba85"
K_LAW_ID = "\ubc95\ub839ID"
K_LAW_SERIAL_ID = "\ubc95\ub839\uc77c\ub828\ubc88\ud638"
K_PROMULGATION_DATE = "\uacf5\ud3ec\uc77c\uc790"
K_EFFECTIVE_DATE = "\uc2dc\ud589\uc77c\uc790"
K_EFFECTIVE_DATE_SHORT = "\uc2dc\ud589\uc77c"
K_CURRENT_STATUS = "\ud604\ud589\uc5ec\ubd80"
K_CURRENT_HISTORY_CODE = "\ud604\ud589\uc5f0\ud601\ucf54\ub4dc"
K_ARTICLE_UNIT = "\uc870\ubb38\ub2e8\uc704"
K_ARTICLE_CONTENT = "\uc870\ubb38\ub0b4\uc6a9"
K_ARTICLE_BODY = "\uc870\ubb38\ubcf8\ubb38"
K_ARTICLE_TITLE = "\uc870\ubb38\uc81c\ubaa9"
K_ARTICLE_NUMBER = "\uc870\ubb38\ubc88\ud638"
K_ARTICLE_NUMBER_TEXT = "\uc870\ubb38\ubc88\ud638\ubb38\uc790\uc5f4"
K_PARAGRAPH_CONTENT = "\ud56d\ub0b4\uc6a9"
K_SUBPARAGRAPH_CONTENT = "\ud638\ub0b4\uc6a9"


class LawSourceProviderUnavailable(Exception):
    pass


class LawSourceProviderError(Exception):
    pass


class LawSourceProvider(Protocol):
    source_type: str

    def get_article_by_law_and_article(
        self,
        law_name: str,
        article_number_text: str,
    ) -> OfficialLawArticleSnapshot | None:
        ...

    def get_law_metadata(self, law_name: str) -> OfficialLawMetadata | None:
        ...

    def search_articles(
        self,
        law_name: str | None = None,
        keyword: str | None = None,
    ) -> list[OfficialLawArticleSnapshot]:
        ...


class MockOfficialLawSourceProvider:
    source_type = "mock_official"

    def __init__(self, articles: list[OfficialLawArticleSnapshot] | None = None) -> None:
        self._articles = articles if articles is not None else _default_mock_articles()

    def get_article_by_law_and_article(
        self,
        law_name: str,
        article_number_text: str,
    ) -> OfficialLawArticleSnapshot | None:
        normalized_law_name = _normalize(law_name)
        normalized_article_number = _normalize_article_number(article_number_text)
        return next(
            (
                article
                for article in self._articles
                if _normalize(article.law_name) == normalized_law_name
                and _normalize_article_number(article.article_number_text) == normalized_article_number
            ),
            None,
        )

    def get_law_metadata(self, law_name: str) -> OfficialLawMetadata | None:
        normalized_law_name = _normalize(law_name)
        matched = [article for article in self._articles if _normalize(article.law_name) == normalized_law_name]
        if not matched:
            return None

        effective_dates = [article.effective_date for article in matched if article.effective_date is not None]
        return OfficialLawMetadata(
            law_name=matched[0].law_name,
            effective_date=min(effective_dates) if effective_dates else None,
            source_url=f"https://mock.official.local/laws/{_url_key(matched[0].law_name)}",
            source_type=self.source_type,
            official_law_id=matched[0].official_law_id,
        )

    def search_articles(
        self,
        law_name: str | None = None,
        keyword: str | None = None,
    ) -> list[OfficialLawArticleSnapshot]:
        normalized_law_name = _normalize(law_name) if law_name else None
        normalized_keyword = _normalize(keyword) if keyword else None

        results = self._articles
        if normalized_law_name:
            results = [article for article in results if _normalize(article.law_name) == normalized_law_name]
        if normalized_keyword:
            results = [
                article
                for article in results
                if normalized_keyword in _normalize(article.article_title or "")
                or normalized_keyword in _normalize(article.article_text)
                or normalized_keyword in _normalize(article.article_number_text)
            ]
        return list(results)


class MolegOpenApiLawSourceProvider:
    source_type = "moleg_open_api"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url if base_url is not None else settings.moleg_api_base_url).strip().rstrip("/")
        self.api_key = (api_key if api_key is not None else settings.moleg_api_key).strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.moleg_api_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def get_article_by_law_and_article(
        self,
        law_name: str,
        article_number_text: str,
    ) -> OfficialLawArticleSnapshot | None:
        search_result = self.search_laws(law_name)
        candidate = search_result.selected_candidate
        if candidate is None or not candidate.mst:
            return None

        document = self.get_law_document(candidate.mst, fallback_title=candidate.title)
        normalized_article_number = _normalize_article_number(article_number_text)
        matched_article = next(
            (
                article
                for article in document.articles
                if _normalize_article_number(article.article_no) == normalized_article_number
                or normalized_article_number in _normalize_article_number(article.article_no)
            ),
            None,
        )
        if matched_article is None:
            if document.articles:
                return _document_article_to_snapshot(document=document, article=document.articles[0])
            return None
        return _document_article_to_snapshot(document=document, article=matched_article)

    def get_law_metadata(self, law_name: str) -> OfficialLawMetadata | None:
        candidate = self.search_laws(law_name).selected_candidate
        if candidate is None:
            return None
        return _candidate_to_metadata(candidate=candidate, source_type=self.source_type)

    def search_articles(
        self,
        law_name: str | None = None,
        keyword: str | None = None,
    ) -> list[OfficialLawArticleSnapshot]:
        if not law_name:
            return []
        search_result = self.search_laws(law_name)
        candidate = search_result.selected_candidate
        if candidate is None or not candidate.mst:
            return []
        document = self.get_law_document(candidate.mst, fallback_title=candidate.title)
        snapshots = [_document_article_to_snapshot(document=document, article=article) for article in document.articles]
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

    def search_laws(self, query: str, page: int = 1, display: int = 20) -> OfficialLawSearchResult:
        json_params = self._search_params(query=query, result_type=MOLEG_JSON_TYPE, page=page, display=display)
        payload = self._request_payload(path=MOLEG_LAW_SEARCH_PATH, params=json_params)
        result = self._normalize_law_search_result(payload=payload, query=query)
        if result.candidates:
            return result

        xml_params = self._search_params(query=query, result_type=MOLEG_XML_TYPE, page=page, display=display)
        xml_payload = self._request_payload(path=MOLEG_LAW_SEARCH_PATH, params=xml_params)
        return self._normalize_law_search_result(payload=xml_payload, query=query, provider_reason="JSON search returned no candidates; XML fallback used.")

    def get_law_document(self, mst: str, fallback_title: str | None = None) -> OfficialLawDocument:
        json_params = self._document_params(mst=mst, result_type=MOLEG_JSON_TYPE)
        payload = self._request_payload(path=MOLEG_LAW_SERVICE_PATH, params=json_params)
        document = self._normalize_law_document(payload=payload, fallback_title=fallback_title, fallback_mst=mst)
        if document.articles:
            return document

        xml_params = self._document_params(mst=mst, result_type=MOLEG_XML_TYPE)
        xml_payload = self._request_payload(path=MOLEG_LAW_SERVICE_PATH, params=xml_params)
        return self._normalize_law_document(
            payload=xml_payload,
            fallback_title=fallback_title,
            fallback_mst=mst,
            provider_reason="JSON document returned no articles; XML fallback used.",
        )

    def search_law_candidates(self, query: str) -> list[OfficialLawMetadata]:
        return [_candidate_to_metadata(candidate, self.source_type) for candidate in self.search_laws(query).candidates]

    def get_law_articles_by_id(self, official_law_id: str, fallback_law_name: str | None = None) -> list[OfficialLawArticleSnapshot]:
        document = self.get_law_document(official_law_id, fallback_title=fallback_law_name)
        return [_document_article_to_snapshot(document=document, article=article) for article in document.articles]

    def _select_law_candidate(self, candidates: list[OfficialLawMetadata], law_name: str) -> OfficialLawMetadata | None:
        normalized_law_name = _normalize(law_name)
        ranked = sorted(
            candidates,
            key=lambda candidate: _candidate_rank(candidate.law_name, None, normalized_law_name, candidate.official_law_id, None)[0],
            reverse=True,
        )
        return ranked[0] if ranked else None

    def _search_params(self, query: str, result_type: str, page: int, display: int) -> dict[str, str]:
        params = self._base_params(result_type=result_type)
        params.update({"target": MOLEG_LAW_TARGET, "query": query, "page": str(page), "display": str(display)})
        return params

    def _document_params(self, mst: str, result_type: str) -> dict[str, str]:
        params = self._base_params(result_type=result_type)
        params.update({"target": MOLEG_LAW_TARGET, "MST": mst})
        return params

    def _base_params(self, result_type: str) -> dict[str, str]:
        return {"OC": self.api_key, "type": result_type}

    def _request_payload(self, path: str, params: dict[str, str]) -> dict[str, Any] | list[Any]:
        if not self.configured:
            raise LawSourceProviderUnavailable("MOLEG API is not configured.")

        try:
            response = httpx.get(
                urljoin(f"{self.base_url}/", path.lstrip("/")),
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "json" in content_type.lower() or params.get("type") == MOLEG_JSON_TYPE:
                try:
                    return response.json()
                except ValueError:
                    if params.get("type") == MOLEG_JSON_TYPE:
                        raise
            return _xml_text_to_dict(response.text)
        except httpx.TimeoutException as exc:
            raise LawSourceProviderError("MOLEG API request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LawSourceProviderError("MOLEG API request failed.") from exc
        except (ValueError, ElementTree.ParseError) as exc:
            raise LawSourceProviderError("MOLEG API response could not be parsed.") from exc

    def _normalize_law_search_result(
        self,
        payload: dict[str, Any] | list[Any],
        query: str,
        provider_reason: str = "",
    ) -> OfficialLawSearchResult:
        records = _extract_dicts_with_any(payload, (K_LAW_NAME_HANGUL, K_LAW_NAME, "lsNm", "MST", K_LAW_ID, "ID"))
        candidates = [candidate for record in records if (candidate := self._normalize_candidate(record=record, query=query))]
        candidates.sort(key=lambda candidate: candidate.match_score, reverse=True)
        pagination = _normalize_pagination(payload)
        status = "matched" if candidates else "unmatched"
        selected_candidate = candidates[0] if candidates else None
        return OfficialLawSearchResult(
            source_mode="live",
            status=status,
            query=query,
            candidates=candidates,
            selected_candidate=selected_candidate,
            pagination=pagination,
            sanitized_source_url=_safe_source_url(self.base_url, MOLEG_LAW_SEARCH_PATH),
            provider_reason=provider_reason or ("Selected exact/highest-ranked law candidate." if selected_candidate else "No law candidates were returned."),
        )

    def _normalize_candidate(self, record: dict[str, Any], query: str) -> OfficialLawCandidate | None:
        title = _first_text(record, "law_name", K_LAW_NAME_HANGUL, K_LAW_NAME, "lsNm")
        mst = _first_text(record, "MST", "mst", K_LAW_SERIAL_ID, "law_serial_id")
        law_id = _first_text(record, K_LAW_ID, "law_id", "ID", "LM", "lm")
        if not title or not (mst or law_id):
            return None
        short_title = _first_text(record, K_LAW_SHORT_NAME, "short_title", "lsAbrvNm")
        score, reason = _candidate_rank(title=title, short_title=short_title, query=_normalize(query), mst=mst, is_current=_parse_current_flag(_first_text(record, K_CURRENT_STATUS, K_CURRENT_HISTORY_CODE, "is_current")))
        return OfficialLawCandidate(
            title=title,
            short_title=short_title,
            law_id=law_id,
            mst=mst or law_id,
            promulgation_date=_parse_date(_first_text(record, K_PROMULGATION_DATE, "promulgation_date", "ancYd")),
            enforcement_date=_parse_date(_first_text(record, K_EFFECTIVE_DATE, K_EFFECTIVE_DATE_SHORT, "effective_date", "efYd")),
            is_current=_parse_current_flag(_first_text(record, K_CURRENT_STATUS, K_CURRENT_HISTORY_CODE, "is_current")),
            source_url=_safe_source_url(self.base_url, MOLEG_LAW_SERVICE_PATH),
            match_score=score,
            match_reason=reason,
            raw_payload_redacted=redact_secret_values(record, self.api_key),
        )

    def _normalize_law_candidates(self, payload: dict[str, Any] | list[Any]) -> list[OfficialLawMetadata]:
        return [_candidate_to_metadata(candidate, self.source_type) for candidate in self._normalize_law_search_result(payload=payload, query="").candidates]

    def _normalize_law_document(
        self,
        payload: dict[str, Any] | list[Any],
        fallback_title: str | None,
        fallback_mst: str,
        provider_reason: str = "",
    ) -> OfficialLawDocument:
        records = _extract_dicts_with_any(payload, (K_ARTICLE_CONTENT, K_ARTICLE_BODY, K_ARTICLE_TITLE, K_ARTICLE_NUMBER, "joCts", "joNo"))
        title = _find_first_text(payload, K_LAW_NAME_HANGUL, K_LAW_NAME, "lsNm") or fallback_title or "UNKNOWN_LAW"
        law_id = _find_first_text(payload, K_LAW_ID, "law_id", "ID", "LM", "lm")
        enforcement_date = _parse_date(_find_first_text(payload, K_EFFECTIVE_DATE, K_EFFECTIVE_DATE_SHORT, "effective_date", "efYd"))
        articles = [article for record in records if (article := _normalize_article(record))]
        return OfficialLawDocument(
            title=title,
            law_id=law_id,
            mst=fallback_mst,
            enforcement_date=enforcement_date,
            articles=articles,
            raw_available=bool(payload),
            normalized_at=datetime.now(UTC),
            provider_reason=provider_reason or ("Article units normalized." if articles else "No article units were normalized."),
            sanitized_source_url=_safe_source_url(self.base_url, MOLEG_LAW_SERVICE_PATH),
            raw_payload_redacted=redact_secret_values(_payload_debug_sample(payload), self.api_key),
        )

    def _normalize_law_articles(
        self,
        payload: dict[str, Any] | list[Any],
        fallback_law_name: str | None,
        fallback_law_id: str,
    ) -> list[OfficialLawArticleSnapshot]:
        document = self._normalize_law_document(payload=payload, fallback_title=fallback_law_name, fallback_mst=fallback_law_id)
        return [_document_article_to_snapshot(document=document, article=article) for article in document.articles]


def make_law_source_provider(source_mode: str = "mock") -> LawSourceProvider:
    if source_mode == "live":
        return MolegOpenApiLawSourceProvider()
    return MockOfficialLawSourceProvider()


def redact_secret_values(value: Any, secret: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: SECRET_REDACTION if key in SECRET_KEYS else redact_secret_values(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secret_values(item, secret) for item in value]
    if isinstance(value, str) and secret and secret in value:
        return value.replace(secret, SECRET_REDACTION)
    return value


def _candidate_to_metadata(candidate: OfficialLawCandidate, source_type: str) -> OfficialLawMetadata:
    return OfficialLawMetadata(
        law_name=candidate.title,
        effective_date=candidate.enforcement_date,
        source_url=candidate.source_url,
        source_type=source_type,
        official_law_id=candidate.mst or candidate.law_id,
        raw_payload_redacted=candidate.raw_payload_redacted,
    )


def _document_article_to_snapshot(document: OfficialLawDocument, article: OfficialLawArticle) -> OfficialLawArticleSnapshot:
    return OfficialLawArticleSnapshot(
        law_name=document.title,
        article_number_text=article.article_no,
        article_title=article.article_title,
        article_text=article.article_text,
        effective_date=document.enforcement_date,
        source_url=document.sanitized_source_url,
        source_type="moleg_open_api" if document.sanitized_source_url.startswith("http") else "mock_official",
        official_law_id=document.mst or document.law_id,
        raw_payload_redacted=document.raw_payload_redacted,
    )


def _normalize_article(record: dict[str, Any]) -> OfficialLawArticle | None:
    article_no = _first_text(record, K_ARTICLE_NUMBER, K_ARTICLE_NUMBER_TEXT, "joNo", "article_number_text")
    article_text = _first_text(record, K_ARTICLE_CONTENT, K_ARTICLE_BODY, "joCts", "article_text")
    if not article_no or not article_text:
        return None
    paragraphs = _extract_paragraphs(record)
    return OfficialLawArticle(
        article_no=article_no,
        article_title=_first_text(record, K_ARTICLE_TITLE, "joTtl", "article_title"),
        article_text=article_text,
        paragraphs=paragraphs,
        source_anchor=_first_text(record, "article_key", "joNo"),
        source_hint="Normalized from MOLEG lawService article unit.",
    )


def _extract_paragraphs(record: dict[str, Any]) -> list[str]:
    paragraphs: list[str] = []
    stack: list[Any] = [record]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if key in {K_PARAGRAPH_CONTENT, K_SUBPARAGRAPH_CONTENT, "paragraph_text", "hangCts", "hoCts"} and str(value).strip():
                    paragraphs.append(str(value).strip())
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)
    return paragraphs


def _candidate_rank(title: str, short_title: str | None, query: str, mst: str | None, is_current: bool | None) -> tuple[int, str]:
    normalized_title = _normalize(title)
    normalized_short_title = _normalize(short_title or "")
    score = 0
    reasons: list[str] = []
    if normalized_title == query:
        score += 100
        reasons.append("exact title match")
    elif normalized_short_title == query:
        score += 85
        reasons.append("exact short title match")
    elif normalized_title.startswith(query):
        score += 65
        reasons.append("title starts with query")
    elif query in normalized_title:
        score += 45
        reasons.append("title contains query")
    if is_current is True:
        score += 10
        reasons.append("current law signal")
    if mst:
        score += 5
        reasons.append("MST present")
    return score, ", ".join(reasons) or "fallback ranking"


def _normalize_pagination(payload: dict[str, Any] | list[Any]) -> OfficialLawPagination | None:
    total_count = _parse_int(_find_first_text(payload, "totalCnt", "total_count", "totalCount", "total"))
    page = _parse_int(_find_first_text(payload, "page", "pageNo", "pageIndex"))
    page_size = _parse_int(_find_first_text(payload, "display", "numOfRows", "pageSize"))
    if total_count is None and page is None and page_size is None:
        return None
    total_pages = ceil(total_count / page_size) if total_count is not None and page_size else None
    return OfficialLawPagination(page=page, page_size=page_size, total_count=total_count, total_pages=total_pages)


def _parse_current_flag(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = _normalize(value)
    if normalized in {"true", "1", "yes", "y", "\ud604\ud589", "\ud604\ud589\ubc95\ub839"}:
        return True
    if normalized in {"false", "0", "no", "n", "\uc5f0\ud601", "\ud3d0\uc9c0"}:
        return False
    return None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _payload_debug_sample(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _payload_debug_sample(value) for key, value in list(payload.items())[:5]}
    if isinstance(payload, list):
        return [_payload_debug_sample(item) for item in payload[:3]]
    return payload


def _xml_text_to_dict(xml_text: str) -> dict[str, Any]:
    root = ElementTree.fromstring(xml_text)
    return {root.tag: _xml_element_to_value(root)}


def _xml_element_to_value(element: ElementTree.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    result: dict[str, Any] = {}
    for child in children:
        child_value = _xml_element_to_value(child)
        if child.tag in result:
            existing = result[child.tag]
            if not isinstance(existing, list):
                result[child.tag] = [existing]
            result[child.tag].append(child_value)
        else:
            result[child.tag] = child_value
    return result


def _extract_dicts_with_any(payload: dict[str, Any] | list[Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    stack: list[Any] = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if any(key in item for key in keys):
                records.append(item)
            stack.extend(reversed(list(item.values())))
        elif isinstance(item, list):
            stack.extend(reversed(item))
    return records


def _first_text(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _find_first_text(payload: dict[str, Any] | list[Any], *keys: str) -> str | None:
    stack: list[Any] = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            value = _first_text(item, *keys)
            if value:
                return value
            stack.extend(reversed(list(item.values())))
        elif isinstance(item, list):
            stack.extend(reversed(item))
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    normalized = value.replace(".", "").replace("-", "").strip()
    if len(normalized) != 8 or not normalized.isdigit():
        return None
    return date(int(normalized[:4]), int(normalized[4:6]), int(normalized[6:8]))


def _safe_source_url(base_url: str, path: str = "") -> str:
    cleaned_base_url = base_url.split("?", 1)[0].rstrip("/")
    if not path:
        return cleaned_base_url
    return urljoin(f"{cleaned_base_url}/", path.lstrip("/"))


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _normalize_article_number(value: str) -> str:
    return _normalize(value).replace(" ", "")


def _url_key(value: str) -> str:
    return _normalize(value).replace(" ", "-")


def _default_mock_articles() -> list[OfficialLawArticleSnapshot]:
    return [
        OfficialLawArticleSnapshot(
            law_name="TEST_LAW_DO_NOT_USE",
            article_number_text="TEST_ARTICLE_DO_NOT_USE",
            article_title="TEST_ARTICLE_TITLE_PROJECT_BASIC_REVIEW_DO_NOT_USE",
            article_text="TEST_VERSION_DO_NOT_USE_CURRENT",
            effective_date=date(2099, 1, 1),
            source_url="https://mock.official.local/laws/test-law/articles/test-article",
            official_law_id="TEST_MOCK_MST_DO_NOT_USE",
        ),
        OfficialLawArticleSnapshot(
            law_name="TEST_LAW_DO_NOT_USE",
            article_number_text="TEST_PARTIAL_ARTICLE_DO_NOT_USE",
            article_title="TEST_OTHER_TITLE_DO_NOT_USE",
            article_text="TEST_PARTIAL_TEXT_DO_NOT_USE",
            effective_date=date(2099, 1, 1),
            source_url="https://mock.official.local/laws/test-law/articles/test-partial",
            official_law_id="TEST_MOCK_MST_DO_NOT_USE",
        ),
        OfficialLawArticleSnapshot(
            law_name="Urban Development Act Fixture",
            article_number_text="Article 3",
            article_title="Urban development zone designation",
            article_text="Mock official source fixture for urban development zone designation review.",
            effective_date=date(2026, 1, 1),
            source_url="https://mock.official.local/laws/urban-development-act/articles/3",
            official_law_id="URBAN_DEV_FIXTURE_MST",
        ),
    ]
