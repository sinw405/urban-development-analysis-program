# Urban Development Analysis Program

This project analyzes general urban development projects with a FastAPI backend, PostgreSQL persistence, Alembic migrations, and YAML-based rule files.

Current stage: Phase 8.

Phase 8 keeps the existing FastAPI, PostgreSQL, Alembic, persistence, YAML rule-engine flow, legal-reference foundation, MOLEG ingest foundation, law version lookup foundation, as_of analysis enrichment, and law update event foundation. It adds a React frontend MVP for submitting analysis requests and reviewing law update events. It does not finalize legal articles, assessment thresholds, or real law data.

## Important Limits

- This application is not a final legal determination tool.
- Legal article numbers are not finalized.
- Environmental impact assessment, traffic impact assessment, underground safety assessment, and buried cultural heritage review thresholds remain TODO/placeholders.
- Assessment thresholds must remain `TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA` until later legal review.
- Real criteria must be finalized later through reviewed MOLEG Open API integration and expert review.
- MOLEG API calls are disabled by default and require explicit environment configuration.

## Windows PowerShell Local Run

```powershell
cd C:\Users\poiu2\Desktop\??????_??_??_????
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For local backend execution outside Docker, use `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/urban_dev` while the Compose PostgreSQL container is running.

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker Compose Run

Start Docker Desktop first, then run from the project root.

```powershell
cd C:\Users\poiu2\Desktop\??????_??_??_????
docker compose up --build --detach
```

Check containers:

```powershell
docker compose ps
```

Stop containers:

```powershell
docker compose down
```

## PostgreSQL Connection

The backend container connects to PostgreSQL through Docker internal networking:

```text
postgres:5432
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/urban_dev
```

Local Python processes on Windows connect through the host port:

```text
localhost:5433
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/urban_dev
```

Host/local database connection:

```text
host: localhost
port: 5433
database: urban_dev
user: postgres
password: postgres
```

## Alembic Migrations

`alembic.ini` is located at the project root. Run Alembic commands from the project root.

```powershell
cd C:\Users\poiu2\Desktop\??????_??_??_????
alembic upgrade head
```

The FastAPI app no longer creates tables automatically on startup. Run migrations before using APIs that touch the database.

## Development DB Reset

In early development, an existing Docker volume may contain tables created before Alembic was introduced. The clean reset flow is:

```powershell
docker compose down -v
docker compose up --build --detach
alembic upgrade head
```

Warning: `docker compose down -v` deletes the PostgreSQL Docker volume and all data stored in it. Use it only when you are intentionally resetting the local development database.

If you want to keep existing development data, do not run `down -v`. The initial migration is written defensively for existing Phase 1 tables, but a clean volume is the recommended baseline during this early phase.

## API Tests

In Windows PowerShell, `curl` can resolve to an `Invoke-WebRequest` alias. Use `curl.exe` for simple GET checks.

### Health

```powershell
curl.exe http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

### Analyze and Store Result

```powershell
$body = @{
  project_name = "Test Urban Development Project"
  location = "Seongnam-si, Gyeonggi-do"
  area_square_meters = 100000
  implementation_method = "Expropriation or use method"
  implementer_type = "Local public corporation"
  local_government = "Seongnam-si"
} | ConvertTo-Json

$result = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/analyze" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body

$result | ConvertTo-Json -Depth 8
```

### List Stored Analyses With Pagination

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/analyses?limit=20&offset=0" -Method Get | ConvertTo-Json -Depth 5
```

Response shape:

```json
{
  "items": [],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

### List Stored Analyses With Filters

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/analyses?project_name=Test&local_government=Seongnam-si&sort=created_at_desc" -Method Get | ConvertTo-Json -Depth 5
```

Supported query parameters:

```text
limit: 1..100, default 20
offset: 0 or greater, default 0
project_name: optional partial match
local_government: optional partial match
sort: created_at_desc or created_at_asc, default created_at_desc
```

### Get Stored Analysis Detail

```powershell
$analysisId = $result.analysis_id
Invoke-RestMethod -Uri "http://localhost:8000/api/analyses/$analysisId" -Method Get | ConvertTo-Json -Depth 8
```


## Phase 2 Rule Engine

Phase 2 standardizes the YAML-based procedure rule engine. It does not add MOLEG Open API integration, RAG, React frontend, legal article finalization, or assessment threshold finalization.

### Procedure Rule Structure

`rules/procedure_rules.yaml` uses this structure:

```yaml
common_steps: []
implementation_method_rules: {}
implementer_type_rules: {}
```

Each procedure step uses the standardized response fields below:

```text
step_code
step_name
sequence
description
required_documents
related_agencies
estimated_duration
legal_basis_placeholder
legal_references
notes
```

Legacy field mapping:

```text
order -> sequence
name -> step_name
legal_basis -> legal_basis_placeholder
consultation_agencies -> related_agencies
```

### Supported Implementation Methods

```text
expropriation_or_use
replotting
mixed
```

Korean compatibility aliases are supported:

```text
?? ?? ?? ??, ?? -> expropriation_or_use
?? ??, ?? -> replotting
?? ??, ?? -> mixed
```

### Supported Implementer Types

```text
public
private
public_private_spc
```

Korean compatibility aliases are supported:

```text
?? -> public
?? -> private
??SPC, ???? SPC -> public_private_spc
```

### Assessment Placeholder Policy

`rules/assessment_rules.yaml` remains placeholder-only.

Required invariant:

```text
threshold = TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA
legal_basis = TODO_MOLEG_API_ARTICLE_CHECK
```

The following are not implemented in Phase 4:

- Environmental impact assessment threshold finalization
- Traffic impact assessment threshold finalization
- Underground safety assessment threshold finalization
- Buried cultural heritage threshold finalization
- MOLEG Open API integration
- RAG
- React frontend

## Phase 3 Legal Reference Foundation

Phase 3 adds database tables for laws, law articles, law article versions, and procedure legal references. These tables are preparation for later MOLEG article mapping only.

Procedure responses now include:

```text
legal_basis_placeholder = TODO_MOLEG_API_ARTICLE_CHECK or another TODO/PENDING placeholder
legal_references = []
```

The Phase 3 legal-reference tables remain placeholder-oriented. Article mapping remains pending until a later reviewed integration phase.

## Phase 4 MOLEG Ingest Foundation

Phase 4 prepares for later MOLEG Open API integration without building real legal criteria or real article mappings.

Environment settings:

```text
MOLEG_API_ENABLED=false
MOLEG_API_BASE_URL=
MOLEG_API_KEY=
```

Default behavior is safe: `MOLEG_API_ENABLED=false`, empty base URL, and empty API key. With these defaults, the application does not perform external MOLEG network calls. The HTTP adapter raises a disabled-configuration error before any request is attempted unless the integration is explicitly enabled and configured.

Phase 4 adds:

```text
MolegHttpAdapter
DisabledMolegAdapter
LawIngestService
MinimalMolegPayloadParser
GET /api/laws
GET /api/laws/{law_id}/articles
```

The ingest service accepts a minimal internal payload shape used by tests and stores rows in `laws`, `law_articles`, and `law_article_versions`. Tests use only `TEST_*_DO_NOT_USE` fake values. Real law names, real article numbers, real assessment thresholds, API keys, external XML parsing, RAG, and React remain out of scope.

## Phase 5 Law Version Lookup Foundation

Phase 5 adds service and internal API support for looking up stored law article versions by an `as_of` date. This works only with data already stored in `laws`, `law_articles`, and `law_article_versions`; it does not call the MOLEG API and does not create real legal criteria.

Version selection rule:

```text
current: latest effective_date less than or equal to as_of
previous: effective_date less than or equal to as_of but older than current
scheduled: effective_date greater than as_of
unknown_effective_date: effective_date is not stored
```

Internal API endpoints:

```text
GET /api/laws
GET /api/laws/{law_id}/articles
GET /api/laws/{law_id}/articles?as_of=YYYY-MM-DD
GET /api/laws/{law_id}/articles/{article_id}/versions
GET /api/laws/{law_id}/articles/{article_id}/versions?as_of=YYYY-MM-DD
```

Phase 5 tests use only `TEST_*_DO_NOT_USE` fixtures, including fake law, article, and version text. Real law names, real article numbers, real thresholds, external MOLEG calls, RAG, and React remain out of scope.

## Phase 6 Analyze Legal Reference Enrichment

Phase 6 lets `POST /api/analyze` accept an optional `as_of` date. When a procedure step has rows in `procedure_legal_references`, the analysis response attaches legal reference metadata and stored law article version status for that date.

Request field:

```text
as_of: optional YYYY-MM-DD
```

If `as_of` is omitted, existing analyze requests still work and legal references remain empty unless a stored procedure reference exists. The response keeps existing top-level fields and adds the optional `as_of` value.

Procedure legal references include only mapping metadata such as IDs, keys, placeholder status, version IDs, effective dates, source, and temporal status. Real law names, real article numbers, and real legal criteria are not hardcoded into analysis results.

Version statuses follow the Phase 5 rules:

```text
current
previous
scheduled
unknown_effective_date
```

Phase 6 tests use only `TEST_*_DO_NOT_USE` law, article, version, and procedure reference fixtures. MOLEG network calls, real legal data, RAG, and React remain out of scope.

## Phase 7 Law Update Detection Foundation

Phase 7 adds an event foundation for stored law article version changes. It compares an internal/fake incoming article version payload with existing `law_article_versions`, creates a `law_update_events` row when a new or changed version is detected, and reports impacted procedure step codes through `procedure_legal_references`.

New table:

```text
law_update_events
```

Internal API endpoints:

```text
GET /api/law-updates
GET /api/law-updates?since=YYYY-MM-DD
GET /api/law-updates/{event_id}
```

Event responses include IDs, change type, detected date, effective date, status, source, and `impacted_step_codes`. They do not include real law names, real article numbers, or final legal criteria.

Phase 7 tests use only `TEST_*_DO_NOT_USE` law, article, version, and procedure reference fixtures. MOLEG network calls remain disabled by default and are not used by update detection tests. RAG and React remain out of scope.

## Phase 8 React Frontend MVP

Phase 8 adds a Vite + React + TypeScript frontend under `frontend/`. The frontend is an MVP for checking backend API behavior from a browser. It does not add real legal data, RAG, MOLEG network calls, or final UI workflows.

Frontend environment:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Local frontend run:

```powershell
cd C:\Users\poiu2\Desktop\도시개발사업_관련_분석_프로그램\frontend
npm install
npm run dev
```

Build/typecheck:

```powershell
npm run typecheck
npm run build
```

Screens:

```text
/             Dashboard with API base URL and navigation
/analyze      Project analysis form calling POST /api/analyze
/law-updates  Law update event list calling GET /api/law-updates
```

The analysis screen displays procedure steps, placeholder assessment values, and legal reference metadata exactly as returned by the backend. If a step has no connected legal references, it shows an empty state. If references exist, it displays backend-provided IDs, status values, effective dates, source, and temporal status only. It does not invent law names, article numbers, or criteria.

FastAPI CORS is configured with `CORS_ALLOWED_ORIGINS`, defaulting to the Vite development origins:

```text
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

The frontend is not added as a Docker Compose service in Phase 8. Keeping it as a local npm workflow avoids adding Node dependency installation to the existing backend/database verification path. A production or containerized frontend can be added later when deployment requirements are clearer.

Baekhyeon MICE may be used only as a generic validation input. There is no Baekhyeon-specific branch, step code, or hardcoded logic.

### Analyze Response Example

`POST /api/analyze` keeps the top-level response fields and standardizes `procedures` items:

```json
{
  "project_name": "Test Urban Development Project",
  "location": "Seongnam-si, Gyeonggi-do",
  "area_square_meters": 100000,
  "implementation_method": "mixed",
  "implementer_type": "public_private_spc",
  "local_government": "Seongnam-si",
  "procedures": [
    {
      "step_code": "PROJECT_BASIC_REVIEW",
      "step_name": "Project basic review",
      "sequence": 10,
      "description": "Review basic project information...",
      "required_documents": [],
      "related_agencies": [],
      "estimated_duration": "TODO_EXPERT_REVIEW",
      "legal_basis_placeholder": ["TODO_MOLEG_API_ARTICLE_CHECK"],
      "legal_references": [],
      "notes": []
    }
  ],
  "assessments": [],
  "warnings": [],
  "project_id": 1,
  "analysis_id": 1,
  "created_at": "2026-07-06T00:00:00Z"
}
```

## Assessment Response Policy

- Do not determine whether an assessment is required in Phase 8.
- Keep thresholds as `TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA`.
- Mark assessment status as legal review required.
- Finalize criteria later through MOLEG Open API and expert review.

## Test Execution Order

Recommended order from the project root:

```powershell
docker compose up --build --detach
alembic upgrade head
python -m pytest
```

Additional checks:

```powershell
docker compose config
docker compose ps
curl.exe http://localhost:8000/health
```

## Git Commit

```powershell
git status
git add .
git commit -m "Add phase 8 react frontend foundation"
git status
```
