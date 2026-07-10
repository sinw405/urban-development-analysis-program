from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import yaml

from app.services.official_law_seed_bootstrap_service import (
    ALLOWED_ARTICLE_STATUSES,
    ALLOWED_LAW_TYPES,
    DEFAULT_SEED_DIR,
    FORBIDDEN_FIELDS,
    SENSITIVE_QUERY_KEYS,
    validate_official_law_seed_directory,
)
from app.services.rule_loader import load_yaml_rule

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_MATERIAL_DIR = ROOT_DIR / "data" / "official_law_source_materials"
INTAKE_TEMPLATE_PATH = DEFAULT_SOURCE_MATERIAL_DIR / "official_seed_batch1_intake_template.csv"
BATCH1_POLICY_PATH = ROOT_DIR / "docs" / "official_seed_batch1_authoring_policy.md"
DEFAULT_TARGET_LAW_KEYS = {
    "urban_development_act",
    "urban_development_act_enforcement_decree",
    "urban_development_act_enforcement_rule",
}


@dataclass
class IntakeRowValidation:
    file_path: str
    row_number: int
    law_key: str | None = None
    article_no: str | None = None
    status: str = "unknown"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class IntakeValidationReport:
    status: str
    source_material_directory: str
    source_material_directory_exists: bool
    files_scanned: int = 0
    template_files: int = 0
    source_rows: int = 0
    valid_rows: int = 0
    rejected_rows: int = 0
    ready_for_seed_generation: bool = False
    raw_payload_policy_ok: bool = True
    secret_exposed: bool = False
    rows: list[IntakeRowValidation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_material_directory": self.source_material_directory,
            "source_material_directory_exists": self.source_material_directory_exists,
            "files_scanned": self.files_scanned,
            "template_files": self.template_files,
            "source_rows": self.source_rows,
            "valid_rows": self.valid_rows,
            "rejected_rows": self.rejected_rows,
            "ready_for_seed_generation": self.ready_for_seed_generation,
            "raw_payload_policy_ok": self.raw_payload_policy_ok,
            "secret_exposed": self.secret_exposed,
            "rows": [row.__dict__ for row in self.rows],
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_official_seed_intake(source_dir: Path | str = DEFAULT_SOURCE_MATERIAL_DIR) -> IntakeValidationReport:
    directory = Path(source_dir)
    report = IntakeValidationReport(
        status="ok",
        source_material_directory=str(directory),
        source_material_directory_exists=directory.exists(),
    )
    if not directory.exists():
        report.status = "source_material_missing"
        report.warnings.append("source material directory does not exist")
        return report

    files = sorted([*directory.glob("*.csv"), *directory.glob("*.yaml"), *directory.glob("*.yml")])
    report.files_scanned = len(files)
    procedure_codes = _procedure_codes()
    for file_path in files:
        if _is_template_file(file_path):
            report.template_files += 1
            continue
        rows, errors = _load_rows(file_path)
        report.errors.extend(errors)
        if errors:
            report.rejected_rows += 1
            continue
        for row_number, row in rows:
            row_result = _validate_row(file_path=file_path, row_number=row_number, row=row, procedure_codes=procedure_codes)
            report.rows.append(row_result)
            report.source_rows += 1
            if row_result.errors:
                report.rejected_rows += 1
                report.errors.extend(f"{file_path}:{row_number}: {error}" for error in row_result.errors)
            else:
                report.valid_rows += 1

    report.raw_payload_policy_ok = not any(_mentions_forbidden(error) for error in report.errors)
    report.secret_exposed = any("sensitive query parameter" in error for error in report.errors)
    if report.rejected_rows:
        report.status = "failed"
    elif report.source_rows == 0:
        report.status = "template_only" if report.template_files else "source_material_missing"
    report.ready_for_seed_generation = report.status == "ok" and report.source_rows > 0 and report.valid_rows == report.source_rows
    return report


def generate_official_seed_from_intake(
    source_dir: Path | str = DEFAULT_SOURCE_MATERIAL_DIR,
    seed_dir: Path | str = DEFAULT_SEED_DIR,
    apply: bool = False,
) -> dict[str, Any]:
    validation = validate_official_seed_intake(source_dir=source_dir)
    if not validation.ready_for_seed_generation:
        return {
            "status": validation.status,
            "apply": apply,
            "files_scanned": validation.files_scanned,
            "source_rows": validation.source_rows,
            "seed_files_planned": 0,
            "articles_planned": 0,
            "seed_files_written": 0,
            "ready_for_seed_generation": False,
            "raw_payload_policy_ok": validation.raw_payload_policy_ok,
            "secret_exposed": validation.secret_exposed,
            "errors": validation.errors,
            "warnings": validation.warnings,
        }

    directory = Path(source_dir)
    target_dir = Path(seed_dir)
    rows = _valid_rows(directory)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_text(row.get("law_key")) or "", []).append(row)

    planned_files: list[dict[str, Any]] = []
    rejected_law_keys: list[str] = []
    for law_key, law_rows in grouped.items():
        target_file = target_dir / f"{law_key}.seed.yaml"
        if target_dir.resolve() == DEFAULT_SEED_DIR.resolve() and law_key not in DEFAULT_TARGET_LAW_KEYS:
            rejected_law_keys.append(law_key)
            continue
        payload = _seed_payload_from_rows(law_key=law_key, rows=law_rows)
        planned_files.append(
            {
                "law_key": law_key,
                "target_file": str(target_file),
                "article_count": len(payload["articles"]),
                "payload": payload,
            }
        )

    if rejected_law_keys:
        return {
            "status": "validation_error",
            "apply": apply,
            "files_scanned": validation.files_scanned,
            "source_rows": validation.source_rows,
            "seed_files_planned": len(planned_files),
            "articles_planned": sum(item["article_count"] for item in planned_files),
            "seed_files_written": 0,
            "ready_for_seed_generation": False,
            "raw_payload_policy_ok": True,
            "secret_exposed": False,
            "errors": [f"unknown law_key for default seed directory: {law_key}" for law_key in rejected_law_keys],
            "warnings": validation.warnings,
        }

    written = 0
    if apply:
        target_dir.mkdir(parents=True, exist_ok=True)
        for item in planned_files:
            target_file = Path(item["target_file"])
            existing = _load_existing_seed(target_file)
            merged = _merge_seed(existing=existing, generated=item["payload"])
            target_file.write_text(yaml.safe_dump(merged, allow_unicode=True, sort_keys=False), encoding="utf-8")
            written += 1
        seed_validation = validate_official_law_seed_directory(seed_dir=target_dir, include_examples=False)
        if seed_validation.rejected_count:
            return {
                "status": "validation_error",
                "apply": apply,
                "files_scanned": validation.files_scanned,
                "source_rows": validation.source_rows,
                "seed_files_planned": len(planned_files),
                "articles_planned": sum(item["article_count"] for item in planned_files),
                "seed_files_written": written,
                "ready_for_seed_generation": False,
                "raw_payload_policy_ok": seed_validation.raw_payload_policy_ok,
                "secret_exposed": False,
                "errors": seed_validation.errors,
                "warnings": validation.warnings + seed_validation.warnings,
            }

    return {
        "status": "ok" if apply else "dry_run",
        "apply": apply,
        "files_scanned": validation.files_scanned,
        "source_rows": validation.source_rows,
        "seed_files_planned": len(planned_files),
        "articles_planned": sum(item["article_count"] for item in planned_files),
        "seed_files_written": written,
        "ready_for_seed_generation": True,
        "raw_payload_policy_ok": True,
        "secret_exposed": False,
        "planned_seed_files": [
            {"law_key": item["law_key"], "target_file": item["target_file"], "article_count": item["article_count"]}
            for item in planned_files
        ],
        "errors": [],
        "warnings": validation.warnings,
    }


def source_intake_status(source_dir: Path | str = DEFAULT_SOURCE_MATERIAL_DIR) -> dict[str, Any]:
    report = validate_official_seed_intake(source_dir=source_dir)
    return {
        "source_material_directory_exists": report.source_material_directory_exists,
        "source_intake_template_exists": INTAKE_TEMPLATE_PATH.exists(),
        "source_intake_status": report.status,
        "source_intake_rows": report.source_rows,
        "source_intake_valid_rows": report.valid_rows,
        "source_intake_rejected_rows": report.rejected_rows,
        "ready_for_seed_generation": report.ready_for_seed_generation,
        "batch1_policy_exists": BATCH1_POLICY_PATH.exists(),
        "batch1_apply_supported": True,
        "last_seed_generation_status_optional": None,
        "raw_payload_policy_ok": report.raw_payload_policy_ok,
        "secret_exposed": report.secret_exposed,
    }


def _load_rows(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], list[str]]:
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [(index, dict(row)) for index, row in enumerate(csv.DictReader(handle), start=2)], []
        payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        if payload is None:
            return [], []
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return [], ["intake yaml must be a list or contain rows list"]
        return [(index, row) for index, row in enumerate(rows, start=1) if isinstance(row, dict)], []
    except Exception as exc:
        return [], [f"intake parse failed: {exc.__class__.__name__}"]


def _valid_rows(directory: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    procedure_codes = _procedure_codes()
    for file_path in sorted([*directory.glob("*.csv"), *directory.glob("*.yaml"), *directory.glob("*.yml")]):
        if _is_template_file(file_path):
            continue
        rows, errors = _load_rows(file_path)
        if errors:
            continue
        for row_number, row in rows:
            validation = _validate_row(file_path=file_path, row_number=row_number, row=row, procedure_codes=procedure_codes)
            if not validation.errors:
                result.append(row)
    return result


def _validate_row(file_path: Path, row_number: int, row: dict[str, Any], procedure_codes: set[str]) -> IntakeRowValidation:
    result = IntakeRowValidation(file_path=str(file_path), row_number=row_number, law_key=_text(row.get("law_key")), article_no=_text(row.get("article_no")))
    _find_forbidden_fields(row, "row", result.errors)
    for key in ("law_key", "law_name", "law_type", "article_no", "article_title", "sanitized_summary", "procedure_codes", "status", "confidence", "is_confirmed"):
        if not _text(row.get(key)):
            result.errors.append(f"{key} is required")
    if not (_text(row.get("article_anchor")) or _text(row.get("official_source_url"))):
        result.errors.append("article_anchor or official_source_url is required")
    if _text(row.get("law_type")) not in ALLOWED_LAW_TYPES:
        result.errors.append(f"law_type must be one of {sorted(ALLOWED_LAW_TYPES)}")
    if _text(row.get("status")) not in ALLOWED_ARTICLE_STATUSES:
        result.errors.append(f"status must be one of {sorted(ALLOWED_ARTICLE_STATUSES)}")
    if _has_sensitive_query(_text(row.get("official_source_url"))):
        result.errors.append("official_source_url contains a sensitive query parameter")
    if _parse_bool(row.get("is_confirmed")) is True and not (_text(row.get("verification_note")) or _text(row.get("verified_by_optional"))):
        result.errors.append("confirmed rows require verification_note or verified_by_optional")
    try:
        confidence = float(str(row.get("confidence")).strip())
        if confidence < 0 or confidence > 1:
            result.errors.append("confidence must be between 0 and 1")
    except (TypeError, ValueError):
        result.errors.append("confidence must be a number between 0 and 1")
    for procedure_code in _split_list(row.get("procedure_codes")):
        if procedure_code not in procedure_codes:
            result.errors.append(f"unknown procedure_code {procedure_code}")
    result.status = "invalid" if result.errors else "valid"
    return result


def _seed_payload_from_rows(law_key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0]
    return {
        "seed_version": "1.0",
        "law_key": law_key,
        "law_name": _text(first.get("law_name")),
        "law_type": _text(first.get("law_type")),
        "source": {
            "source_type": "official_manual",
            "source_name": "official_seed_batch1_intake",
            "source_url_optional": _safe_url(first.get("official_source_url")),
            "retrieved_at_optional": _text(first.get("source_checked_at_optional")),
            "verified_by_optional": _text(first.get("verified_by_optional")),
            "verification_note_optional": _text(first.get("verification_note")),
        },
        "articles": [_article_payload(row) for row in rows],
    }


def _article_payload(row: dict[str, Any]) -> dict[str, Any]:
    article_no = _text(row.get("article_no"))
    return {
        "article_key": _text(row.get("article_key")) or f"{_text(row.get('law_key'))}:{article_no}:{_text(row.get('article_anchor')) or _safe_url(row.get('official_source_url'))}",
        "article_no": article_no,
        "article_title": _text(row.get("article_title")),
        "article_anchor": _text(row.get("article_anchor")) or _safe_url(row.get("official_source_url")),
        "sanitized_summary": _text(row.get("sanitized_summary")),
        "effective_date_optional": _text(row.get("effective_date_optional")),
        "promulgation_date_optional": _text(row.get("promulgation_date_optional")),
        "status": _text(row.get("status")) or "unknown",
        "procedure_codes": _split_list(row.get("procedure_codes")),
        "tags": _split_list(row.get("tags")),
        "source_mode_detail": "official_seed_db",
        "confidence": float(str(row.get("confidence")).strip()),
        "is_confirmed": _parse_bool(row.get("is_confirmed")),
        "confirmation_note": _text(row.get("verification_note")),
    }


def _merge_seed(existing: dict[str, Any] | None, generated: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return generated
    merged = dict(existing)
    merged["source"] = generated["source"]
    existing_articles = list(merged.get("articles") or [])
    seen = {(_text(item.get("article_key")), _text(item.get("article_no")), _text(item.get("article_anchor"))) for item in existing_articles if isinstance(item, dict)}
    for article in generated["articles"]:
        key = (_text(article.get("article_key")), _text(article.get("article_no")), _text(article.get("article_anchor")))
        if key not in seen:
            existing_articles.append(article)
            seen.add(key)
    merged["articles"] = existing_articles
    return merged


def _load_existing_seed(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else None


def _find_forbidden_fields(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in FORBIDDEN_FIELDS:
                errors.append(f"{path}: forbidden field {key} is present")
            _find_forbidden_fields(item, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _find_forbidden_fields(item, f"{path}[{index}]", errors)


def _procedure_codes() -> set[str]:
    rules = load_yaml_rule("procedure_rules.yaml")
    result: set[str] = set()
    for section in ("procedures", "common_steps", "conditional_steps", "steps"):
        for step in rules.get(section, []):
            if isinstance(step, dict) and step.get("step_code"):
                result.add(str(step["step_code"]))
    return result


def _is_template_file(path: Path) -> bool:
    name = path.name.lower()
    return "template" in name or "example" in name


def _split_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    separator = ";" if ";" in text else ","
    return [item.strip() for item in text.split(separator) if item.strip()]


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes", "y"}


def _has_sensitive_query(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(str(url))
    return any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True))


def _safe_url(url: Any) -> str | None:
    if not url:
        return None
    parsed = urlparse(str(url))
    if not parsed.scheme or not parsed.netloc:
        return None
    return parsed._replace(query="", fragment="").geturl()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mentions_forbidden(value: str) -> bool:
    lowered = value.lower()
    return any(field in lowered for field in FORBIDDEN_FIELDS)
