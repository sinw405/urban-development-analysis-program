from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Law, LawAttachedTableEvidence

K_LAW = "법령"
K_TABLES = "별표"
K_TABLE_UNIT = "별표단위"
K_NUMBER = "별표번호"
K_TITLE = "별표제목"
K_CONTENT = "별표내용"
SOURCE = "MOLEG_LIVE_ATTACHED_TABLE"


@dataclass(frozen=True)
class ParsedAttachedTable:
    table_key: str
    table_number: str
    table_title: str
    mst: str
    effective_date: date | None
    normalized_text: str
    source: str = SOURCE


def normalize_attached_table_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text).strip()


def parse_attached_table_payload(payload: dict[str, Any] | list[Any], mst: str, effective_date: date | None) -> list[ParsedAttachedTable]:
    root = payload.get(K_LAW, payload) if isinstance(payload, dict) else {}
    container = root.get(K_TABLES, {}) if isinstance(root, dict) else {}
    units = container.get(K_TABLE_UNIT, []) if isinstance(container, dict) else []
    if isinstance(units, dict):
        units = [units]
    if not isinstance(units, list):
        return []
    parsed: list[ParsedAttachedTable] = []
    seen: set[str] = set()
    for index, unit in enumerate(units, start=1):
        if not isinstance(unit, dict):
            continue
        number = normalize_attached_table_text(unit.get(K_NUMBER)) or str(index)
        title = normalize_attached_table_text(unit.get(K_TITLE))
        content = normalize_attached_table_text(unit.get(K_CONTENT))
        if not title or not content:
            continue
        key = f"table:{number}"
        if key in seen:
            continue
        seen.add(key)
        parsed.append(ParsedAttachedTable(key, number, title, str(mst), effective_date, content))
    return parsed


def sync_attached_table_evidence(db: Session, law: Law, payload: dict[str, Any] | list[Any], mst: str, effective_date: date | None) -> list[LawAttachedTableEvidence]:
    records: list[LawAttachedTableEvidence] = []
    for parsed in parse_attached_table_payload(payload, mst=mst, effective_date=effective_date):
        record = db.scalar(select(LawAttachedTableEvidence).where(
            LawAttachedTableEvidence.law_id == law.id,
            LawAttachedTableEvidence.table_key == parsed.table_key,
            LawAttachedTableEvidence.mst == parsed.mst,
        ))
        if record is None:
            record = LawAttachedTableEvidence(law_id=law.id, table_key=parsed.table_key, mst=parsed.mst)
            db.add(record)
        record.table_number = parsed.table_number
        record.table_title = parsed.table_title
        record.effective_date = parsed.effective_date
        record.normalized_text = parsed.normalized_text
        record.source = parsed.source
        record.provenance_json = {"source": parsed.source, "mst": parsed.mst, "raw_payload_stored": False, "secret_exposed": False}
        record.verified_at = datetime.now(UTC)
        records.append(record)
    db.flush()
    return records


def resolve_attached_table_evidence(db: Session, law_name: str, table_number: str, as_of: date) -> LawAttachedTableEvidence | None:
    raw_number = str(table_number).strip()
    canonical_number = raw_number.lstrip("0") or "0"
    number_candidates = {raw_number, canonical_number, canonical_number.zfill(4)}
    return db.scalar(
        select(LawAttachedTableEvidence)
        .join(Law)
        .where(
            Law.law_name == law_name,
            LawAttachedTableEvidence.table_number.in_(number_candidates),
            LawAttachedTableEvidence.effective_date.is_not(None),
            LawAttachedTableEvidence.effective_date <= as_of,
        )
        .order_by(LawAttachedTableEvidence.effective_date.desc(), LawAttachedTableEvidence.id.desc())
        .limit(1)
    )
