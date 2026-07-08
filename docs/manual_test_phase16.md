# Phase 16 Manual QA Checklist

## Goal

Phase 16 packages the current v0.1 MVP documentation and verifies that the project remains stable after release-readiness cleanup. It does not add new product features, backend APIs, DB migrations, or real legal datasets.

## Final Routes

```text
/
/analyze
/analyses
/analyses/{existingAnalysisId}
/analyses/999999
/law-updates
```

## Backend Pytest Result

Record the latest result after running:

```powershell
docker compose exec backend pytest
```

Expected release result: `51 passed, 1 warning`.

## Demo Seed Result

Run:

```powershell
docker compose exec backend python -m app.dev_seed
```

Expected result: command succeeds and returns TEST-only seed identifiers.

## Frontend Typecheck Result

Run:

```powershell
cd frontend
npm run typecheck
```

Expected result: success.

## Frontend Build Result

Run:

```powershell
cd frontend
npm run build
```

Expected result: success.

## Browser Verification

Confirm that these pages open without a fatal layout or routing error:

```text
/
/analyze
/analyses
/analyses/{existingAnalysisId}
/analyses/999999
/law-updates
```

## PDF Output Verification

Confirm browser print-to-PDF output for:

```text
/analyses/{existingAnalysisId}
/analyze
```

Server-side PDF generation remains deferred.

## README Link Verification

Confirm README links or references exist for:

```text
docs/release_notes_v0.1.md
docs/final_feature_summary.md
docs/known_limitations.md
docs/manual_test_phase15.md
docs/manual_test_phase16.md
```

## Release Documents

```text
release_notes_v0.1.md: 작성됨
final_feature_summary.md: 작성됨
known_limitations.md: 작성됨
manual_test_phase16.md: 작성됨
```

## Raw JSON Policy

Raw JSON remains limited to the developer detail section. It should not appear in normal roadmap, checklist, or report sections.

## Data Missing Policy

```text
근거 미연결
기관 확인 필요
서류 확인 필요
기간 확인 필요
미확인
```

## API and DB Compatibility

Phase 16 should not change backend API response shapes, DB schema, Alembic migrations, or `analysis_results.result_payload` storage.

## Git Status

Before committing Phase 16, expected changed files are documentation only:

```text
README.md
docs/release_notes_v0.1.md
docs/final_feature_summary.md
docs/known_limitations.md
docs/manual_test_phase16.md
```

## Tag Hold

Do not create the `v0.1-mvp` tag during Phase 16 unless explicitly approved by the user. Suggested command after approval:

```powershell
git tag -a v0.1-mvp -m "v0.1 MVP release"
```
