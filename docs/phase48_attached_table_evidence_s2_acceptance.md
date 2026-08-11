# Phase 48 Attached Table Evidence and S2 Acceptance

## 구현 결과

Phase 47에서 확인한 공식 MOLEG 별표 구조만 재사용했다. `LawAttachedTableEvidence`는 법령 FK, 별표 식별자·제목, MST, 시행일, 공백 정규화 본문, provenance, verified timestamp를 저장한다. `(law_id, table_key, mst)` unique constraint로 동일 version 적재를 멱등 처리한다.

기존 `run_moleg_live_ingest` transaction이 법령 상세 payload를 조문과 함께 별표 parser에 전달한다. 별도의 MOLEG client나 수집기를 만들지 않았다. `resolve_attached_table_evidence`는 분석일 이하에서 가장 최신 effective date만 선택하고 과거에 evidence가 없으면 `None`을 반환한다.

## Production 연결 결과 (2026-08-11 기준)

| Assessment | 법령/MST | 별표 | DB evidence | Applicability | Threshold |
|---|---|---|---|---|---|
| 환경영향평가 | 환경영향평가법 시행령 / 279237 | 3 | resolved | PARTIAL | PLACEHOLDER |
| 교통영향평가 | 도시교통정비 촉진법 시행령 / 287283 | 1 | resolved | PARTIAL | PLACEHOLDER |
| 재해영향 검토 | 자연재해대책법 시행령 / 282993 | 1 | resolved | PARTIAL | PLACEHOLDER |
| 지하안전평가 | 지하안전관리에 관한 특별법 시행령 / 283007 | 1 | resolved | PARTIAL | PLACEHOLDER |

4개 시행령 380개 조문과 31개 별표 evidence가 기존 Live ingest로 적재됐다. 별표 행/열·각주·예외를 아직 구조화하지 않았으므로 공식 표가 도시개발사업을 포함한다는 provenance와 자동 적용조건은 구분한다. VERIFIED applicability와 VERIFIED numeric threshold는 0건이며 추측값은 없다.

## 안전 상태

- 도시계획위원회 심의와 경관심의: `applicability_status=local_rule_required`, `local_rule_required=true`
- 교육환경 및 매장유산: `unresolved`
- 입력 부족: 기존 `NEED_MORE_INFO`
- 전문가 검토 flag: 기존 `requires_expert_review` 유지
- 근거 없는 REQUIRED/NOT_REQUIRED: 0건

기존 `POST /api/analyze` contract는 유지하고 `local_rule_required`, evidence ID, resolved effective date, as-of status만 additive로 제공한다.

## Threshold validation

VERIFIED threshold는 value, unit, operator, project category, source law, source locator, effective date가 모두 있어야 한다. operator는 `gt/gte/lt/lte/eq`만 허용한다. 불완전·비수치·placeholder 기준은 자동판정에 사용되지 않는다.

## S2 Final Acceptance

| 항목 | 결과 |
|---|---|
| T2.1 표준 절차 그래프 | COMPLETE |
| T2.2 시행방식 분기 | COMPLETE |
| T2.3 시행자 유형 분기 | COMPLETE |
| T2.4 심의·평가 판별 | COMPLETE |
| T2.5 Rule config/loader | COMPLETE |
| T2.6 analyze service | COMPLETE |
| T2.7 regression/version management | COMPLETE |

T2.4 COMPLETE는 모든 항목의 강제 자동판정을 의미하지 않는다. verified evidence 기반 자동판정 gate, 입력 부족, 지자체 규칙, 전문가 검토, unresolved 상태가 서로 구분되고 근거 없는 REQUIRED/NOT_REQUIRED가 생성되지 않는 것을 acceptance 기준으로 삼는다.

## 남은 범위

별표 row-level parser와 전문가 승인된 전국 공통 threshold 등록은 후속 고도화 대상이다. 자치법규 수집 없이 지역 기준을 전국 공통 규칙으로 만들지 않는다. 이 항목들은 안전한 S2 판별 contract를 막지 않는다.

## 보안

API key, OC query, 전체 인증 URL, raw exception은 저장하지 않는다. 별표 provenance에는 source/MST와 `secret_exposed=false`, `raw_payload_stored=false`만 기록한다.
