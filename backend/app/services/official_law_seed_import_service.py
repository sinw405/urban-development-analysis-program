from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.official_law_source import OfficialLawSeedImportResponse, OfficialLawSeedManifest
from app.services.official_law_manual_import_service import import_official_law_file

SEED_SOURCE_MODE = "official_seed"
SEED_SOURCE_MODE_DETAIL = "official_seed_db"
SEED_EVIDENCE_TYPE = "official_seed_normalized_summary"
PLACEHOLDER_PREFIX = "<"
PLACEHOLDER_SUFFIX = ">"


def import_official_law_seed(db: Session, manifest_path: str) -> OfficialLawSeedImportResponse:
    manifest_file = Path(manifest_path).expanduser()
    warnings: list[str] = []
    try:
        manifest, source_file = _preflight_manifest(manifest_file, warnings)
    except SeedValidationError as exc:
        return OfficialLawSeedImportResponse(
            success=False,
            status="validation_error",
            source_mode=SEED_SOURCE_MODE,
            source_mode_detail=SEED_SOURCE_MODE_DETAIL,
            reason_type="validation_error",
            error_message_sanitized=str(exc),
            warnings=warnings,
            secret_exposed=False,
        )

    response = import_official_law_file(
        db=db,
        file_path=str(source_file),
        query=manifest.law_title,
        source_provider=manifest.source_provider,
        source_mode=SEED_SOURCE_MODE,
        evidence_type=SEED_EVIDENCE_TYPE,
        run_type="official_law_seed_import",
    )
    warnings.extend(_metadata_warnings(manifest))
    if response.article_count < manifest.expected_min_article_count:
        warnings.append(f"article_count {response.article_count} is below expected_min_article_count {manifest.expected_min_article_count}.")

    return OfficialLawSeedImportResponse(
        success=response.status == "success",
        status=response.status,
        source_mode=SEED_SOURCE_MODE,
        source_mode_detail=SEED_SOURCE_MODE_DETAIL,
        document_id=response.document_id,
        document_count=1 if response.document_id is not None else 0,
        article_count=response.article_count,
        ingest_run_id=response.ingest_run_id,
        ingest_status=response.status,
        source_provider=manifest.source_provider,
        law_title=manifest.law_title,
        law_id=manifest.law_id,
        mst=manifest.mst,
        enforcement_date=manifest.enforcement_date,
        secret_exposed=False,
        evidence_type=SEED_EVIDENCE_TYPE if response.status == "success" else None,
        warnings=warnings,
        reason_type=response.reason_type,
        error_message_sanitized=response.error_message_sanitized,
    )


def _preflight_manifest(manifest_file: Path, warnings: list[str]) -> tuple[OfficialLawSeedManifest, Path]:
    if not manifest_file.exists() or not manifest_file.is_file():
        raise SeedValidationError("manifest file does not exist")
    try:
        raw = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        manifest = OfficialLawSeedManifest.model_validate(raw)
    except Exception as exc:
        raise SeedValidationError(f"manifest could not be parsed: {exc.__class__.__name__}") from exc

    _reject_placeholder_manifest(raw)
    if manifest.mode not in {"official_seed", "manual_seed"}:
        raise SeedValidationError("mode must be official_seed or manual_seed")
    if manifest.source_format not in {"json", "xml"}:
        raise SeedValidationError("source_format must be json or xml")
    if not manifest.source_provider.strip():
        raise SeedValidationError("source_provider is required")
    if not manifest.law_title.strip():
        raise SeedValidationError("law_title is required")
    if manifest.expected_min_article_count < 1:
        raise SeedValidationError("expected_min_article_count must be at least 1")

    source_file = Path(manifest.source_file)
    if not source_file.is_absolute():
        source_file = manifest_file.parent / source_file
    if not source_file.exists() or not source_file.is_file():
        raise SeedValidationError("source_file does not exist")
    if source_file.suffix.lower().lstrip(".") != manifest.source_format:
        raise SeedValidationError("source_file extension does not match source_format")
    return manifest, source_file


def _reject_placeholder_manifest(value: Any) -> None:
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            stripped = item.strip()
            if stripped.startswith(PLACEHOLDER_PREFIX) and stripped.endswith(PLACEHOLDER_SUFFIX):
                raise SeedValidationError("placeholder manifest values cannot be imported")


def _metadata_warnings(manifest: OfficialLawSeedManifest) -> list[str]:
    warnings: list[str] = []
    if not manifest.law_id:
        warnings.append("law_id is empty; stored document identity will rely on normalized payload and MST if available.")
    if not manifest.mst:
        warnings.append("mst is empty; stored document identity will rely on normalized payload and law_id if available.")
    if not manifest.enforcement_date:
        warnings.append("enforcement_date is empty; version distinction may be weaker.")
    return warnings


class SeedValidationError(Exception):
    pass
