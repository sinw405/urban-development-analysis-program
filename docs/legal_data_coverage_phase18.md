# Phase 18 Legal Data Coverage

## Scope

Phase 18 expands legal reference coverage for the core common procedure flow by using the existing TEST seed and legal reference structure. It does not finalize actual law names, article numbers, article titles, agencies, required documents, or criteria.

The intended legal domain for later review is urban development project law data, including statute, enforcement decree, and enforcement rule materials. In Phase 18, those official mappings remain verification-required and are not treated as verified data.

## Verification Status Policy

```text
검증 완료: Official source and expert review completed. Not used in Phase 18.
후보 연결: TEST legal reference structure is connected to a procedure step for coverage verification.
검증 필요: Candidate requires official source, article, ordinance, agency, document, and expert validation.
근거 미연결: No legal reference is connected to the step.
```

Phase 18 uses `TODO_MOLEG_API_ARTICLE_CHECK`, `PENDING_MOLEG_API_MAPPING`, and TEST-only keys to keep every expanded reference in 후보 연결 / 검증 필요 status.

## Data Creation Locations Rechecked

```text
rules/procedure_rules.yaml: core procedure steps and workflow placeholders
backend/app/services/dev_seed_service.py: TEST law, TEST articles, TEST versions, and procedure_legal_references
backend/app/services/legal_reference_service.py: step_code-based legal reference attachment
backend/app/services/analyzer.py: result_payload procedure construction
frontend/src/utils/analysisSummary.ts: display normalization and counts
frontend/src/components/ProcedureStepDetail.tsx: step-level legal reference display
frontend/src/components/AnalysisReport.tsx: report counts and missing-data summaries
```

## Core Common Procedure Review Table

| Step code | Step name | Legal reference status | Law name | Article number/title | Documents | Agencies | Duration | Confirmation-required items |
|---|---|---|---|---|---|---|---|---|
| PROJECT_BASIC_REVIEW | Project basic review | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 기간 |
| ZONE_DESIGNATION_REVIEW | Urban development zone designation proposal or review | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 기간 |
| RESIDENT_OPINION_HEARING | Resident opinion hearing and public notice | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 기간, 지자체 조례 |
| RELATED_AGENCY_CONSULTATION | Related agency consultation | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 기관, 기간 |
| URBAN_PLANNING_COMMITTEE_REVIEW | Urban planning committee review | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 심의 요건, 기간 |
| ZONE_DESIGNATION_NOTIFICATION | Zone designation and public notification | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 권한, 기간 |
| DEVELOPMENT_PLAN_ESTABLISHMENT | Development plan establishment | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 계획 내용, 기간 |
| IMPLEMENTER_DESIGNATION_REVIEW | Implementer designation review | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 서류 확인 필요 | 기관 확인 필요 | 기간 확인 필요 | 실제 조문, 서류, 기관, 기간 |
| IMPLEMENTATION_PLAN_AUTHORIZATION | Implementation plan authorization | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 첨부서류, 기간 |
| PROJECT_IMPLEMENTATION | Project implementation and construction | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 변경인가 조건, 기간 |
| COMPLETION_INSPECTION | Completion inspection and project closeout | 후보 연결 / 검증 필요 | TEST_LAW_DO_NOT_USE | TEST_ARTICLE_DO_NOT_USE | 있음 | 있음 | 기간 확인 필요 | 실제 조문, 준공 조건, 기간 |

## Coverage Summary

```text
Core common procedure candidate count: 11
TEST candidate legal reference connected core steps: 11
Verified legal reference connected core steps: 0
Verification-required candidate reference steps: 11
Unconnected core steps after demo seed: 0
Steps with document candidates: 10
Steps requiring document confirmation: 1
Steps with agency candidates: 10
Steps requiring agency confirmation: 1
Steps with confirmed duration: 0
Steps requiring duration confirmation: 11
Article URLs verified: 0
```

## Legal Reference Expansion

`backend/app/services/dev_seed_service.py` now creates TEST-only law article records and procedure legal references for all 11 core common procedure steps. These are candidate connections for UI/report coverage verification, not verified legal mappings.

The law update event remains tied to `PROJECT_BASIC_REVIEW` only so the `/law-updates` screen continues to show one focused TEST event without implying every core step changed.

## Link Policy

The frontend does not create blank article links. When no verified article URL exists, the step detail displays:

```text
링크 확인 필요
```

## Remaining Verification Work

```text
Official legal article source verification
Article number and title verification
Article URL verification
Required document verification
Responsible agency verification
Duration or schedule guidance verification
Local ordinance and local practice review
Expert review before any verified status is used
```
