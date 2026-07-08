# Phase 18 Manual Test

## Goal

Phase 18 expands TEST legal reference coverage for the 11 core common procedure steps while keeping actual legal article mappings verification-required. It does not add new screens, DB migrations, server PDF generation, or automatic legal original-text collection.

## Phase 17 Commit Check

```text
Phase 17 commit: 4ce2ad6 Improve legal data coverage for core procedures
v0.1-mvp tag target: 519328fd9cf76dbad445ab87efa02b8b96734ee3
```

## Core Procedure Recheck

Confirm that the core common procedure set includes 11 steps:

```text
PROJECT_BASIC_REVIEW
ZONE_DESIGNATION_REVIEW
RESIDENT_OPINION_HEARING
RELATED_AGENCY_CONSULTATION
URBAN_PLANNING_COMMITTEE_REVIEW
ZONE_DESIGNATION_NOTIFICATION
DEVELOPMENT_PLAN_ESTABLISHMENT
IMPLEMENTER_DESIGNATION_REVIEW
IMPLEMENTATION_PLAN_AUTHORIZATION
PROJECT_IMPLEMENTATION
COMPLETION_INSPECTION
```

## New Analysis Test

1. Run demo seed.
2. Submit a TEST analysis with `mixed` and `public_private_spc` inputs.
3. Confirm that core common steps each have one TEST legal reference candidate.
4. Confirm that method/implementer branch steps can still remain `근거 미연결` unless separately connected.

## Stored Analysis Detail Test

Open `/analyses/{analysisId}` for a new Phase 18 analysis. Confirm that stored `result_payload` displays the expanded legal reference candidates in roadmap, detail, and report sections.

## Roadmap Legal Reference Display

Confirm that:

```text
Core common steps show candidate legal reference counts.
Unconnected non-core branch steps still show 근거 미연결.
IMPLEMENTER_DESIGNATION_REVIEW still shows 서류 확인 필요, 기관 확인 필요, and 기간 확인 필요.
No empty article URL is rendered.
No verified article number is displayed.
```

## Report Count Check

Confirm that the report summary reflects the expanded TEST candidate references:

```text
Core common procedure reference candidates: 11
Verified legal mappings: 0
Verification-required candidate mappings: 11
```

The report counts are display counts from current result data, not legal validation results.

## Verification Status Policy

```text
검증 완료: not used in Phase 18
후보 연결: TEST legal reference connected for coverage verification
검증 필요: official source/expert validation required
근거 미연결: no reference connected
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

Raw JSON remains limited to the developer detail area and is not part of normal roadmap, checklist, or report display.

## API and DB Compatibility

Phase 18 keeps backend API response shapes, DB schema, Alembic migrations, and `analysis_results.result_payload` storage compatible with previous phases.

## Test Commands

```powershell
docker compose up --build --detach
docker compose exec backend alembic upgrade head
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
No verified actual law article mapping yet.
No final legal criteria or thresholds.
No automatic legal original-text collection.
No server-side PDF generation.
No local ordinance integration.
No expert-reviewed required-document or agency dataset.
```
