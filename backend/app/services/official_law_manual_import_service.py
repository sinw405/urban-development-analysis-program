from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.official_law_source import OfficialLawManualImportResponse
from app.services.moleg_live_client import _xml_text_to_dict, redact_secret_values
from app.services.official_law_persistence_service import (
    INGEST_STATUS_SOURCE_ERROR,
    INGEST_STATUS_SUCCESS,
    add_source_evidence,
    complete_ingest_run,
    create_ingest_run,
    persist_official_law_document,
)
from app.services.official_law_source import MolegOpenApiLawSourceProvider

MANUAL_SOURCE_MODE = "official_manual"
MANUAL_EVIDENCE_TYPE = "manual_import_normalized_summary"


def import_official_law_file(
    db: Session,
    file_path: str,
    query: str | None = None,
    source_provider: str = "moleg_manual_upload",
    source_mode: str = MANUAL_SOURCE_MODE,
) -> OfficialLawManualImportResponse:
    path = Path(file_path).expanduser()
    run = create_ingest_run(db=db, query=query or path.name, source_mode=source_mode, run_type="official_law_manual_import")
    try:
        payload = _load_payload(path)
        provider = MolegOpenApiLawSourceProvider(base_url="manual://official-law-file", api_key="MANUAL_IMPORT_NO_SECRET")
        search_result = provider._normalize_law_search_result(payload=payload, query=query or path.stem)
        selected = search_result.selected_candidate
        document = provider._normalize_law_document(
            payload=payload,
            fallback_title=(None if selected is None else selected.title) or query or path.stem,
            fallback_mst=(None if selected is None else selected.mst) or _extract_mst(payload) or path.stem,
            provider_reason="Normalized from manual official-law file import.",
        )
        if not document.articles:
            complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SOURCE_ERROR, search_result=search_result, document=document, error_reason="invalid_response")
            add_source_evidence(db=db, run=run, evidence_type="manual_import_parse_error", summary={"file_name": path.name, "reason_type": "invalid_response"}, raw_available=False)
            db.commit()
            return OfficialLawManualImportResponse(
                status=INGEST_STATUS_SOURCE_ERROR,
                source_mode=source_mode,
                source_provider=source_provider,
                ingest_run_id=run.id,
                reason_type="invalid_response",
                error_message_sanitized="Manual import file did not contain normalizable article units.",
                secret_exposed=False,
            )

        stored = persist_official_law_document(db=db, document=document, selected_candidate=selected, source_provider=source_provider, source_mode=source_mode)
        complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SUCCESS, search_result=search_result, document=document)
        add_source_evidence(
            db=db,
            run=run,
            evidence_type=MANUAL_EVIDENCE_TYPE,
            summary=redact_secret_values(
                {
                    "file_name": path.name,
                    "source_mode": source_mode,
                    "source_provider": source_provider,
                    "selected_title": None if selected is None else selected.title,
                    "selected_mst": None if selected is None else selected.mst,
                    "document_title": document.title,
                    "document_mst": document.mst,
                    "article_count": len(document.articles),
                    "sanitized_source_url": document.sanitized_source_url,
                }
            ),
            raw_available=True,
        )
        db.commit()
        return OfficialLawManualImportResponse(
            status=INGEST_STATUS_SUCCESS,
            source_mode=source_mode,
            source_provider=source_provider,
            document_id=stored.id,
            ingest_run_id=run.id,
            article_count=len(document.articles),
            provider_reason=document.provider_reason,
            secret_exposed=False,
        )
    except Exception as exc:
        complete_ingest_run(db=db, run=run, status=INGEST_STATUS_SOURCE_ERROR, error_reason="parse_error")
        add_source_evidence(db=db, run=run, evidence_type="manual_import_parse_error", summary={"file_name": path.name, "reason_type": "parse_error", "error_class": exc.__class__.__name__}, raw_available=False)
        db.commit()
        return OfficialLawManualImportResponse(
            status=INGEST_STATUS_SOURCE_ERROR,
            source_mode=source_mode,
            source_provider=source_provider,
            ingest_run_id=run.id,
            reason_type="parse_error",
            error_message_sanitized=exc.__class__.__name__,
            secret_exposed=False,
        )


def _load_payload(path: Path) -> dict[str, Any] | list[Any]:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Manual import file was not found.")
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(text)
        if not isinstance(payload, (dict, list)):
            raise ValueError("JSON root must be an object or array.")
        return payload
    if suffix == ".xml":
        return _xml_text_to_dict(text)
    raise ValueError("Manual import supports only JSON or XML files.")


def _extract_mst(payload: Any) -> str | None:
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key in ("MST", "mst", "법령일련번호"):
                value = item.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return None
