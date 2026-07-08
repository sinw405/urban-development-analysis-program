# Phase 17 Manual Test

## Goal

Phase 17 improves first-pass legal-data coverage for core procedure results while preserving the v0.1 MVP API, DB schema, placeholder policy, and browser report behavior.

## v0.1-mvp Tag Check

```text
Tag exists: v0.1-mvp
Tag target commit: 519328fd9cf76dbad445ab87efa02b8b96734ee3
Tag message: v0.1 MVP release
```

The tag was already present before Phase 17 and was not recreated.

## Data Generation Locations Checked

```text
rules/procedure_rules.yaml
backend/app/services/analyzer.py
backend/app/services/legal_reference_service.py
backend/app/services/dev_seed_service.py
backend/app/models/law.py
backend/app/models/law_article.py
backend/app/models/law_article_version.py
backend/app/models/procedure_legal_reference.py
frontend/src/utils/analysisSummary.ts
frontend/src/components/ProcedureRoadmap.tsx
frontend/src/components/ProcedureStepDetail.tsx
frontend/src/components/AnalysisReport.tsx
```

## Result Payload Fields Checked

```text
procedures[].step_code
procedures[].step_name
procedures[].sequence
procedures[].description
procedures[].required_documents
procedures[].related_agencies
procedures[].estimated_duration
procedures[].legal_basis_placeholder
procedures[].legal_references
procedures[].notes
```

## New Analysis Test

Run a TEST-only analysis from `/analyze` or through `/api/analyze`. Confirm that the result includes the core workflow candidates and that `IMPLEMENTER_DESIGNATION_REVIEW` appears as a confirmation-required step.

## Stored Analysis Detail Test

Open `/analyses/{analysisId}` after running a new analysis. Confirm that the stored result payload displays through the same roadmap, checklist, and report components.

## Roadmap Legal Reference Display

Confirm that:

```text
PROJECT_BASIC_REVIEW shows the TEST legal reference after demo seed.
Unconnected steps show 근거 미연결.
IMPLEMENTER_DESIGNATION_REVIEW shows 서류 확인 필요, 기관 확인 필요, and 기간 확인 필요.
Legal reference cards do not create empty links and show 링크 확인 필요 when no verified URL exists.
```

## Report Legal Reference Counts

Confirm that report summary counts are derived from normalized result data:

```text
전체 절차 수
근거 법령 연결 수
근거 미연결 수
서류 확인 필요
기관 확인 필요
기간 확인 필요
```

## Missing Data Policy

```text
법령 근거 없음: 근거 미연결
기관 없음: 기관 확인 필요
필요 서류 없음: 서류 확인 필요
기간 없음 또는 TODO 기간: 기간 확인 필요
상태 없음: 미확인
조문 URL 없음: 링크 확인 필요
```

## Raw JSON Policy

Raw JSON remains available only in the developer detail section and is not displayed in the normal roadmap, checklist, or report sections.

## API and DB Compatibility

Phase 17 does not change backend API response shapes, Alembic migrations, or `analysis_results.result_payload` storage. It adds no DB migration.

## Test Commands

```powershell
docker compose exec backend pytest
docker compose exec backend python -m app.dev_seed
cd frontend
npm run typecheck
npm run build
```

## Browser Routes

```text
/
/analyze
/analyses
/analyses/{analysisId}
/analyses/999999
/law-updates
```

## Remaining Limitations

```text
Actual legal article mappings remain unverified.
No actual law article number or criteria is finalized.
Automatic MOLEG original-text collection remains out of scope.
Server PDF generation remains out of scope.
Required documents, agencies, and durations still require official and expert confirmation.
```
