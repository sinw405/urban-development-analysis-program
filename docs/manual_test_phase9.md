# Phase 9 Manual Test Checklist

This checklist uses only TEST_*_DO_NOT_USE demo data.

## 1. Start Backend

```powershell
cd C:\Users\poiu2\Desktop\도시개발사업_관련_분석_프로그램
docker compose up --build --detach
docker compose exec backend alembic upgrade head
```

## 2. Seed Demo Data

```powershell
docker compose exec backend python -m app.dev_seed
```

Expected output includes IDs for:

```text
law_id
article_id
current_version_id
scheduled_version_id
procedure_legal_reference_id
law_update_event_id
test_project_name = TEST_PROJECT_DO_NOT_USE
test_step_code = PROJECT_BASIC_REVIEW
```

The command is idempotent. Running it again should return the same IDs instead of creating duplicates.

## 3. Start Frontend

```powershell
cd C:\Users\poiu2\Desktop\도시개발사업_관련_분석_프로그램\frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## 4. Analyze Screen

Open:

```text
http://localhost:5173/analyze
```

Use the default TEST values:

```text
project_name = TEST_PROJECT_DO_NOT_USE
location = TEST_LOCATION_DO_NOT_USE
area_m2 = 100000
method = mixed
operator_type = public_private_spc
local_government = TEST_LOCAL_GOVERNMENT_DO_NOT_USE
as_of = 2099-06-15
```

Expected result:

```text
Procedure steps are displayed.
PROJECT_BASIC_REVIEW has connected legal reference metadata.
Legal reference shows law_id, article_id, law_key, article_key, current version, scheduled version, source, and effective_date.
No real law name, real article number, or legal threshold is displayed.
```

## 5. Law Updates Screen

Open:

```text
http://localhost:5173/law-updates
```

Expected result:

```text
At least one TEST law update event is displayed.
impacted_step_codes includes PROJECT_BASIC_REVIEW.
No real law name, real article number, or legal threshold is displayed.
```

## 6. API Spot Checks

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/api/law-updates
```

Use the frontend form or an API client for `POST /api/analyze`.

## Notes

- MOLEG network calls remain disabled by default.
- RAG and production React workflows are not implemented in Phase 9.
- Demo data is development-only and must not be treated as legal criteria.
