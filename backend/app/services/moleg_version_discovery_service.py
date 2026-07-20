from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from math import ceil
from typing import Any, Iterable
import hashlib

from sqlalchemy.orm import Session

from app.schemas.official_law_source import OfficialLawCandidate, OfficialLawDocument
from app.services.law_version_impact_service import LawVersionImpactResult, LawVersionImpactService
from app.services.moleg_live_client import (
    MOLEG_LAW_SEARCH_PATH,
    MOLEG_LAW_SERVICE_PATH,
    MOLEG_XML_TYPE,
    MolegLiveClient,
    MolegLiveClientError,
    parse_response,
    _parse_response_payload,
    sanitized_url,
)
from app.services.moleg_live_ingest_service import (
    PARSER_VERSION,
    plan_persistence,
    sync_official_document,
    _add_evidence,
    _complete_ingest_run,
    _create_ingest_run,
    _date_to_yyyymmdd,
    _sync_law_tables,
)
from app.services.official_law_source import MolegOpenApiLawSourceProvider

MOLEG_EFLAW_TARGET = "eflaw"
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 20
DEFAULT_MAX_ITEMS = 1000


@dataclass(frozen=True)
class LawVersionDescriptor:
    law_id: str | None
    law_name: str
    mst: str
    promulgation_date: date | None
    enforcement_date: date | None
    promulgation_number: str | None
    revision_type: str | None
    status: str | None
    source: str = "moleg_open_api"
    sanitized_endpoint_name: str = "lawSearch"
    response_content_hash: str | None = None
    parser_version: str = PARSER_VERSION
    result_code: str | None = None
    result_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "law_id": self.law_id,
            "law_name": self.law_name,
            "mst": self.mst,
            "promulgation_date": None if self.promulgation_date is None else self.promulgation_date.isoformat(),
            "enforcement_date": None if self.enforcement_date is None else self.enforcement_date.isoformat(),
            "effective_date": None if self.enforcement_date is None else self.enforcement_date.isoformat(),
            "promulgation_number": self.promulgation_number,
            "revision_type": self.revision_type,
            "status": self.status,
            "source": self.source,
            "sanitized_endpoint_name": self.sanitized_endpoint_name,
            "response_content_hash": self.response_content_hash,
            "parser_version": self.parser_version,
            "result_code": self.result_code,
            "result_message": self.result_message,
        }


@dataclass(frozen=True)
class LawVersionPairSelection:
    law_name: str
    from_version: LawVersionDescriptor
    to_version: LawVersionDescriptor
    selection_reason: str

    @property
    def from_mst(self) -> str:
        return self.from_version.mst

    @property
    def to_mst(self) -> str:
        return self.to_version.mst

    def to_dict(self) -> dict[str, Any]:
        return {
            "law_name": self.law_name,
            "from_mst": self.from_mst,
            "to_mst": self.to_mst,
            "from_promulgation_date": _date_text(self.from_version.promulgation_date),
            "to_promulgation_date": _date_text(self.to_version.promulgation_date),
            "from_effective_date": _date_text(self.from_version.enforcement_date),
            "to_effective_date": _date_text(self.to_version.enforcement_date),
            "from_history_status": self.from_version.status,
            "to_history_status": self.to_version.status,
            "selection_reason": self.selection_reason,
        }


@dataclass
class LawVersionDiscoveryResult:
    status: str
    law_name: str
    requested_at: datetime
    received_at: datetime | None = None
    result_code: str | None = None
    result_message: str | None = None
    total_count: int | None = None
    page_count: int = 0
    requested_pages: list[int] = field(default_factory=list)
    num_of_rows: int | None = None
    collected_item_count: int = 0
    exact_match_count: int = 0
    distinct_mst_count: int = 0
    versions: list[LawVersionDescriptor] = field(default_factory=list)
    selected_pair: tuple[LawVersionDescriptor, LawVersionDescriptor] | None = None
    selection: LawVersionPairSelection | None = None
    sanitized_url: str | None = None
    response_content_hash: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    secret_exposed: bool = False
    raw_payload_stored: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = self.__dict__.copy()
        payload["requested_at"] = self.requested_at.isoformat()
        payload["received_at"] = None if self.received_at is None else self.received_at.isoformat()
        payload["versions"] = [item.to_dict() for item in self.versions]
        payload["selected_pair"] = None if self.selected_pair is None else [self.selected_pair[0].to_dict(), self.selected_pair[1].to_dict()]
        payload["selection"] = None if self.selection is None else self.selection.to_dict()
        return payload


@dataclass
class LiveVersionIngestResult:
    status: str
    dry_run: bool
    law_name: str
    requested_msts: list[str]
    inserted_official_document_count: int = 0
    updated_official_document_count: int = 0
    skipped_official_document_count: int = 0
    inserted_official_article_count: int = 0
    updated_official_article_count: int = 0
    skipped_official_article_count: int = 0
    parsed_article_count: int = 0
    provenance: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rollback: bool = False
    secret_exposed: bool = False
    raw_payload_stored: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class LiveLawChangeImpactResult:
    status: str
    law_name: str
    source: str = "MOLEG"
    mode: str = "auto"
    discovery: LawVersionDiscoveryResult | None = None
    selection: LawVersionPairSelection | None = None
    impact: LawVersionImpactResult | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    secret_exposed: bool = False
    raw_payload_stored: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "law_name": self.law_name,
            "source": self.source,
            "mode": self.mode,
            "discovery": None if self.discovery is None else self.discovery.to_dict(),
            "selection": None if self.selection is None else self.selection.to_dict(),
            "impact": None if self.impact is None else self.impact.to_dict(),
            "warnings": self.warnings,
            "errors": self.errors,
            "checked_at": self.checked_at.isoformat(),
            "secret_exposed": self.secret_exposed,
            "raw_payload_stored": self.raw_payload_stored,
        }


def discover_law_versions(
    client: MolegLiveClient,
    law_name: str,
    max_versions: int = 6,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> LawVersionDiscoveryResult:
    requested_at = datetime.now(UTC)
    result = LawVersionDiscoveryResult(status="started", law_name=law_name, requested_at=requested_at)
    first_params = eflaw_search_params(client=client, query=law_name, display=page_size, page=1)
    result.sanitized_url = sanitized_url(client.sanitized_base_url, MOLEG_LAW_SEARCH_PATH, first_params)
    try:
        pages = fetch_eflaw_search_pages(client=client, law_name=law_name, page_size=page_size, max_pages=max_pages, max_items=max_items, result=result)
        result.received_at = datetime.now(UTC)
        laws = [item for page in pages for item in page.get("laws", [])]
        result.collected_item_count = len(laws)
        versions = normalize_law_versions(laws, law_name=law_name, result=result)
        result.exact_match_count = len(versions)
        versions = sort_law_versions(deduplicate_versions(versions, result=result))
        result.distinct_mst_count = len(versions)
        result.versions = versions[:max_versions]
        result.selection = select_latest_version_pair(versions, law_name=law_name)
        result.selected_pair = None if result.selection is None else (result.selection.from_version, result.selection.to_version)
        result.status = "ok" if versions else "no_versions"
        if result.selection is None:
            result.errors.append("different_mst_pair_not_found" if len(versions) >= 1 else "no_exact_law_versions")
        return result
    except Exception as exc:
        result.received_at = datetime.now(UTC)
        result.status = "source_error"
        result.errors.append(str(exc) or exc.__class__.__name__)
        return result


def fetch_eflaw_search_pages(
    client: MolegLiveClient,
    law_name: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_items: int = DEFAULT_MAX_ITEMS,
    result: LawVersionDiscoveryResult | None = None,
) -> list[dict[str, Any]]:
    safe_page_size = max(1, min(page_size, max_items))
    pages: list[dict[str, Any]] = []
    expected_pages: int | None = None
    total_page_size: int | None = None
    page = 1
    while page <= max_pages:
        params = eflaw_search_params(client=client, query=law_name, display=safe_page_size, page=page)
        response = client._request(MOLEG_LAW_SEARCH_PATH, params)
        content_hash = hashlib.sha256(response.content).hexdigest()
        payload = _parse_response_payload(response)
        search = parse_eflaw_list_response(payload)
        if result is not None:
            result.response_content_hash = content_hash if result.response_content_hash is None else result.response_content_hash
            result.result_code = search.get("result_code")
            result.result_message = search.get("result_msg")
            result.total_count = search.get("total_cnt")
            if result.num_of_rows is None:
                result.num_of_rows = search.get("num_of_rows") or safe_page_size
            result.requested_pages.append(page)
            result.page_count = len(result.requested_pages)
        laws = search.get("laws", [])
        if page > 1 and not laws:
            raise MolegLiveClientError("empty_intermediate_page")
        pages.append(search)
        total_count = search.get("total_cnt")
        row_count = search.get("num_of_rows") or safe_page_size
        if total_page_size is None:
            total_page_size = row_count or safe_page_size
        if total_count is None:
            expected_pages = page if len(laws) < safe_page_size else page + 1
        else:
            expected_pages = max(1, ceil(total_count / max(1, total_page_size)))
        if sum(len(item.get("laws", [])) for item in pages) >= max_items:
            if result is not None:
                result.warnings.append("max_items_reached")
            break
        if page >= expected_pages or (total_count is None and len(laws) < safe_page_size):
            break
        page += 1
    if page >= max_pages and expected_pages is not None and expected_pages > max_pages and result is not None:
        result.warnings.append("max_pages_reached")
    return pages


def eflaw_search_params(client: MolegLiveClient, query: str, display: int = DEFAULT_PAGE_SIZE, page: int = 1) -> dict[str, str]:
    return {
        "OC": client.api_key,
        "type": MOLEG_XML_TYPE,
        "target": MOLEG_EFLAW_TARGET,
        "query": query,
        "nw": "1,2,3",
        "display": str(display),
        "page": str(page),
        "sort": "ddes",
    }


def parse_eflaw_list_response(payload: Any) -> dict[str, Any]:
    root = _find_mapping(payload, {"LawSearch", "lawSearch", "EflawSearch", "eflawSearch", "root"})
    if root is None and isinstance(payload, dict):
        root = payload
    if not isinstance(root, dict):
        raise MolegLiveClientError("invalid_eflaw_response")
    result_code = _first_text(root, "resultCode", "resultcode", "RESULT_CODE")
    if result_code and result_code not in {"00", "0", "success", "SUCCESS"}:
        raise MolegLiveClientError("api_error_response")
    laws = _collect_law_items(root)
    return {
        "result_code": result_code,
        "result_msg": _first_text(root, "resultMsg", "resultmsg", "RESULT_MSG"),
        "total_cnt": _int(_first_text(root, "totalCnt", "totalcnt", "totalCount")),
        "page": _int(_first_text(root, "page", "pageNo")),
        "num_of_rows": _int(_first_text(root, "numOfRows", "numofrows", "display")),
        "laws": [_parse_eflaw_item(item) for item in laws],
    }


def normalize_law_versions(items: Iterable[dict[str, Any]], law_name: str, result: LawVersionDiscoveryResult | None = None) -> list[LawVersionDescriptor]:
    versions: list[LawVersionDescriptor] = []
    for item in items:
        descriptor = normalize_law_version(item, law_name=law_name, result=result)
        if descriptor is not None:
            versions.append(descriptor)
    return versions


def normalize_law_version(item: dict[str, Any], law_name: str, result: LawVersionDiscoveryResult | None = None) -> LawVersionDescriptor | None:
    title = item.get("law_name")
    mst = item.get("mst")
    if normalize_law_name(title) != normalize_law_name(law_name):
        return None
    if not mst:
        if result is not None:
            result.warnings.append("missing_mst")
        return None
    mst_text = str(mst).strip()
    if _mst_number(mst_text) is None and result is not None:
        result.warnings.append(f"invalid_mst:{mst_text}")
    return LawVersionDescriptor(
        law_id=item.get("law_id"),
        law_name=" ".join(str(title).strip().split()),
        mst=mst_text,
        promulgation_date=_parse_yyyymmdd(item.get("promulgation_date")),
        enforcement_date=_parse_yyyymmdd(item.get("effective_date")),
        promulgation_number=item.get("promulgation_no"),
        revision_type=item.get("revision_type"),
        status=item.get("history_status"),
        sanitized_endpoint_name="lawSearch:eflaw",
        response_content_hash=None if result is None else result.response_content_hash,
        result_code=None if result is None else result.result_code,
        result_message=None if result is None else result.result_message,
    )


def deduplicate_versions(versions: Iterable[LawVersionDescriptor], result: LawVersionDiscoveryResult | None = None) -> list[LawVersionDescriptor]:
    by_mst: dict[str, LawVersionDescriptor] = {}
    for version in versions:
        existing = by_mst.get(version.mst)
        if existing is None or _version_sort_key(version) > _version_sort_key(existing):
            if existing is not None and result is not None:
                result.warnings.append(f"duplicate_mst:{version.mst}")
            by_mst[version.mst] = version
        elif result is not None:
            result.warnings.append(f"duplicate_mst:{version.mst}")
    return list(by_mst.values())


def sort_law_versions(versions: Iterable[LawVersionDescriptor]) -> list[LawVersionDescriptor]:
    return sorted(versions, key=_version_sort_key, reverse=True)


def select_exact_law_versions(items: list[dict[str, Any]], law_name: str, normalized_law_id: str | None = None, result: LawVersionDiscoveryResult | None = None) -> list[LawVersionDescriptor]:
    versions = normalize_law_versions(items, law_name=law_name, result=result)
    if normalized_law_id is not None:
        versions = [item for item in versions if normalize_law_id(item.law_id) == normalized_law_id]
    return sort_law_versions(deduplicate_versions(versions, result=result))


def select_latest_version_pair(versions: list[LawVersionDescriptor], law_name: str | None = None) -> LawVersionPairSelection | None:
    sorted_versions = sort_law_versions(deduplicate_versions(versions))
    for index, current in enumerate(sorted_versions):
        for previous in sorted_versions[index + 1:]:
            same_law_id = normalize_law_id(current.law_id) == normalize_law_id(previous.law_id)
            if current.mst != previous.mst and (same_law_id or current.law_id is None or previous.law_id is None):
                return LawVersionPairSelection(
                    law_name=law_name or current.law_name,
                    from_version=previous,
                    to_version=current,
                    selection_reason="sorted_by_effective_date_promulgation_date_mst_desc",
                )
    return None


def select_current_previous_pair(versions: list[LawVersionDescriptor]) -> tuple[LawVersionDescriptor, LawVersionDescriptor] | None:
    selection = select_latest_version_pair(versions)
    return None if selection is None else (selection.from_version, selection.to_version)


def select_current_and_previous_mst(versions: list[LawVersionDescriptor]) -> tuple[LawVersionDescriptor, LawVersionDescriptor] | None:
    return select_current_previous_pair(versions)


def validate_version_pair(versions: list[LawVersionDescriptor], from_mst: str, to_mst: str) -> tuple[LawVersionPairSelection | None, str | None]:
    if from_mst == to_mst:
        return None, "same_mst_not_comparable"
    by_mst = {version.mst: version for version in versions}
    from_version = by_mst.get(str(from_mst))
    to_version = by_mst.get(str(to_mst))
    if from_version is not None and to_version is not None and _version_sort_key(from_version) > _version_sort_key(to_version):
        return None, "from_mst_newer_than_to_mst"
    if from_version is not None and to_version is not None:
        return LawVersionPairSelection(from_version.law_name, from_version, to_version, "manual_mst_selection_validated_against_discovery"), None
    from_number = _mst_number(str(from_mst))
    to_number = _mst_number(str(to_mst))
    if from_number is not None and to_number is not None and from_number > to_number:
        return None, "from_mst_newer_than_to_mst"
    return None, None


def analyze_live_law_change(
    db: Session,
    client: MolegLiveClient,
    law_name: str,
    from_mst: str | None = None,
    to_mst: str | None = None,
    dry_run: bool = True,
    force_rollback: bool = False,
    max_versions: int = 50,
) -> LiveLawChangeImpactResult:
    mode = "manual" if from_mst or to_mst else "auto"
    result = LiveLawChangeImpactResult(status="started", law_name=law_name, mode=mode)
    discovery = discover_law_versions(client=client, law_name=law_name, max_versions=max_versions)
    result.discovery = discovery
    result.warnings.extend(discovery.warnings)
    if discovery.status != "ok":
        result.status = discovery.status
        result.errors.extend(discovery.errors)
        return result
    selection = discovery.selection
    if from_mst or to_mst:
        if not from_mst or not to_mst:
            result.status = "invalid_request"
            result.errors.append("from_mst_and_to_mst_required_together")
            return result
        manual_selection, error = validate_version_pair(discovery.versions, str(from_mst), str(to_mst))
        if error is not None:
            result.status = "invalid_version_pair"
            result.errors.append(error)
            return result
        if manual_selection is not None:
            selection = manual_selection
        else:
            selection = LawVersionPairSelection(
                law_name=law_name,
                from_version=_manual_descriptor(law_name, str(from_mst)),
                to_version=_manual_descriptor(law_name, str(to_mst)),
                selection_reason="manual_mst_selection_not_found_in_discovery_dates_unverified",
            )
    if selection is None:
        result.status = "different_mst_pair_not_found"
        result.errors.append("different_mst_pair_not_found")
        return result
    result.selection = selection
    impact = LawVersionImpactService(db).analyze(law_name, selection.from_mst, selection.to_mst, dry_run=dry_run, force_rollback=force_rollback)
    result.impact = impact
    result.status = "ok" if impact.status == "ok" else impact.status
    result.errors.extend(impact.errors)
    return result


def normalize_law_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if not digits:
        return None
    return str(int(digits))


def normalize_law_name(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def ingest_law_versions(db: Session, client: MolegLiveClient, descriptors: list[LawVersionDescriptor], dry_run: bool = True, force_rollback: bool = False) -> LiveVersionIngestResult:
    result = LiveVersionIngestResult(status="started", dry_run=dry_run, law_name=descriptors[0].law_name if descriptors else "", requested_msts=[item.mst for item in descriptors])
    if not descriptors:
        result.status = "no_versions"
        result.errors.append("no_descriptors")
        return result
    provider = MolegOpenApiLawSourceProvider(base_url=client.base_url, api_key=client.api_key, timeout_seconds=client.timeout_seconds)
    try:
        documents: list[tuple[LawVersionDescriptor, OfficialLawDocument, OfficialLawCandidate, str]] = []
        for descriptor in descriptors:
            params = client.document_params(descriptor.mst, result_type=MOLEG_XML_TYPE, ef_yd=_date_to_yyyymmdd(descriptor.enforcement_date))
            response = client._request(MOLEG_LAW_SERVICE_PATH, params)
            received_at = datetime.now(UTC)
            content_hash = hashlib.sha256(response.content).hexdigest()
            payload = parse_response(response).payload
            document = provider._normalize_law_document(payload=payload, fallback_title=descriptor.law_name, fallback_mst=descriptor.mst)
            if document.enforcement_date is None:
                document.enforcement_date = descriptor.enforcement_date
            if document.law_id is None:
                document.law_id = descriptor.law_id
            if not document.articles:
                result.status = "source_error"
                result.errors.append(f"empty_articles:{descriptor.mst}")
                db.rollback()
                return result
            candidate = _candidate_from_descriptor(descriptor, client)
            documents.append((descriptor, document, candidate, content_hash))
            result.parsed_article_count += len(document.articles)
            result.provenance.append({
                "source_type": "moleg_open_api",
                "law_id": descriptor.law_id,
                "law_name": descriptor.law_name,
                "mst": descriptor.mst,
                "requested_at": datetime.now(UTC).isoformat(),
                "received_at": received_at.isoformat(),
                "normalized_content_hash": _document_hash(document),
                "response_content_hash": content_hash,
                "parser_version": PARSER_VERSION,
                "sanitized_endpoint_name": "lawService",
                "result_code": descriptor.result_code,
                "result_message": descriptor.result_message,
                "raw_payload_stored": False,
                "secret_exposed": False,
            })
        for descriptor, document, candidate, _content_hash in documents:
            current_descriptor = documents[-1][0]
            counters = plan_persistence(db=db, document=document, selected_candidate=candidate, version_status=_version_status_for_descriptor(descriptor, current_descriptor))
            result.inserted_official_document_count += counters.inserted_official_document_count
            result.updated_official_document_count += counters.updated_official_document_count
            result.skipped_official_document_count += counters.skipped_official_document_count
            result.inserted_official_article_count += counters.inserted_official_article_count
            result.updated_official_article_count += counters.updated_official_article_count
            result.skipped_official_article_count += counters.skipped_official_article_count
            if not dry_run:
                run = _create_ingest_run(db=db, law_name=descriptor.law_name)
                official_document = sync_official_document(db=db, document=document, selected_candidate=candidate, counters=counters)
                _sync_law_tables(db=db, document=document, selected_candidate=candidate, counters=counters, version_status=_version_status_for_descriptor(descriptor, current_descriptor))
                _add_evidence(db=db, run=run, document=document, selected=candidate, selected_endpoint=client.sanitized_base_url, trust_env=client.trust_env, version_status=_version_status_for_descriptor(descriptor, current_descriptor))
                _complete_ingest_run(db=db, run=run, status="success", selected=candidate, article_count=len(document.articles), candidate_count=1)
                result.provenance[-1]["official_document_id"] = official_document.id
        if force_rollback:
            raise RuntimeError("PHASE41_TEST_ROLLBACK")
        if dry_run:
            db.rollback()
            result.status = "ready"
        else:
            db.commit()
            result.status = "completed"
        return result
    except Exception as exc:
        db.rollback()
        result.status = "rolled_back" if not dry_run else "source_error"
        result.rollback = not dry_run
        result.errors.append(exc.__class__.__name__)
        return result


def _find_mapping(value: Any, names: set[str]) -> dict[str, Any] | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in names and isinstance(child, dict):
                return child
        for child in value.values():
            found = _find_mapping(child, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_mapping(child, names)
            if found is not None:
                return found
    return None


def _collect_law_items(root: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in ("law", "Law", "eflaw", "Eflaw", "item", "items"):
        value = root.get(key)
        if isinstance(value, dict):
            nested_item = value.get("item")
            if isinstance(nested_item, dict):
                candidates.append(nested_item)
            elif isinstance(nested_item, list):
                candidates.extend(item for item in nested_item if isinstance(item, dict))
            else:
                candidates.append(value)
        elif isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    if candidates:
        return candidates
    nested = root.get("body") or root.get("Body") or root.get("response")
    if isinstance(nested, dict):
        return _collect_law_items(nested)
    return []


def _parse_eflaw_item(item: dict[str, Any]) -> dict[str, Any]:
    law_id = _first_text(item, "\ubc95\ub839ID", "lawId", "law_id")
    return {
        "law_name": _first_text(item, "\ubc95\ub839\uba85\ud55c\uae00", "\ubc95\ub839\uba85", "lawName", "law_name"),
        "mst": _first_text(item, "\ubc95\ub839\uc77c\ub828\ubc88\ud638", "MST", "mst", "lsiSeq"),
        "law_id": law_id,
        "law_id_normalized": normalize_law_id(law_id),
        "promulgation_date": _first_text(item, "\uacf5\ud3ec\uc77c\uc790", "promulgationDate", "promulgation_date"),
        "promulgation_no": _first_text(item, "\uacf5\ud3ec\ubc88\ud638", "promulgationNo", "promulgation_no"),
        "revision_type": _first_text(item, "\uc81c\uac1c\uc815\uad6c\ubd84\uba85", "revisionType", "revision_type"),
        "effective_date": _first_text(item, "\uc2dc\ud589\uc77c\uc790", "effectiveDate", "effective_date"),
        "history_status": _first_text(item, "\ud604\ud589\uc5f0\ud601\ucf54\ub4dc", "historyCode", "status"),
        "detail_link_sanitized": _sanitize_detail_link(_first_text(item, "\ubc95\ub839\uc0c1\uc138\ub9c1\ud06c", "detailLink", "link")),
    }


def _first_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _sanitize_detail_link(value: str | None) -> str | None:
    if not value:
        return None
    sanitized = value
    for token in ("OC=", "oc=", "serviceKey=", "ServiceKey="):
        if token in sanitized:
            prefix, rest = sanitized.split(token, 1)
            suffix = ""
            if "&" in rest:
                suffix = "&" + rest.split("&", 1)[1]
            sanitized = prefix + token + "[REDACTED]" + suffix
    return sanitized


def _version_sort_key(item: LawVersionDescriptor) -> tuple[date, date, int]:
    return (item.enforcement_date or date.min, item.promulgation_date or date.min, _mst_number(item.mst) or 0)


def _mst_number(value: str | None) -> int | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _manual_descriptor(law_name: str, mst: str) -> LawVersionDescriptor:
    return LawVersionDescriptor(
        law_id=None,
        law_name=law_name,
        mst=mst,
        promulgation_date=None,
        enforcement_date=None,
        promulgation_number=None,
        revision_type=None,
        status=None,
        sanitized_endpoint_name="manual",
    )


def _candidate_from_descriptor(descriptor: LawVersionDescriptor, client: MolegLiveClient) -> OfficialLawCandidate:
    return OfficialLawCandidate(
        title=descriptor.law_name,
        law_id=descriptor.law_id,
        mst=descriptor.mst,
        promulgation_date=descriptor.promulgation_date,
        enforcement_date=descriptor.enforcement_date,
        is_current=descriptor.status in {"?袁る뻬", "current"},
        source_url=sanitized_url(client.sanitized_base_url, MOLEG_LAW_SERVICE_PATH, client.document_params(descriptor.mst, result_type=MOLEG_XML_TYPE, ef_yd=_date_to_yyyymmdd(descriptor.enforcement_date))) or "",
        match_score=100,
        match_reason="phase42 exact descriptor",
    )


def _version_status_for_descriptor(descriptor: LawVersionDescriptor, current: LawVersionDescriptor) -> str:
    return "current" if descriptor.mst == current.mst else "historical"


def _document_hash(document: OfficialLawDocument) -> str:
    parts = [document.title, document.law_id or "", document.mst or "", str(document.enforcement_date or "")]
    for article in document.articles:
        parts.extend([article.article_no, article.article_title or "", " ".join((article.article_text or "").split())])
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _parse_yyyymmdd(value: str | None) -> date | None:
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def _date_text(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# Backward-compatible private name used by Phase 41 tests/imports in local scripts.
def _normalize(value: str | None) -> str:
    return normalize_law_name(value)
