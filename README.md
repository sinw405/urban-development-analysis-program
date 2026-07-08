# Urban Development Analysis Program

This project analyzes general urban development projects with a FastAPI backend, PostgreSQL persistence, Alembic migrations, and YAML-based rule files.

Current version: v0.1 MVP. This is a local execution version for demonstrating the urban development project procedure analysis flow. Actual permitting decisions require original legal text, permitting authority consultation, and expert review.

Phase 9 keeps the existing backend foundations and React frontend MVP. It adds a TEST-only local demo seed and manual browser verification flow for analysis legal references and law update events. It does not finalize legal articles, assessment thresholds, or real law data.

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
cd C:\Users\poiu2\Desktop\?????諛몃마嶺뚮??껆빊?潁뺛깷?????⑥쥓???????????곸궔???????⑥ル츧癲???????諛몃마??λ??????얜?沅싷┼??뀕????frontend
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

## Phase 9 Local Demo Testing Flow

Phase 9 adds a development-only demo seed for browser testing. It creates only `TEST_*_DO_NOT_USE` data and is idempotent.

Seed command:

```powershell
docker compose exec backend python -m app.dev_seed
```

Demo data includes:

```text
TEST_LAW_DO_NOT_USE
TEST_ARTICLE_DO_NOT_USE
TEST_VERSION_DO_NOT_USE_CURRENT
TEST_VERSION_DO_NOT_USE_SCHEDULED
TEST_PROJECT_DO_NOT_USE
PROJECT_BASIC_REVIEW procedure legal reference
TEST law update event with impacted_step_codes
```

After seeding, open the frontend:

```powershell
cd C:\Users\poiu2\Desktop\?????밸븶筌믩끃異?縕ュㅇ???怨좊땷?????????댁삩??????怨쀫뮝力???????밸븶?ⓥ뮧????臾믩궚嶺뚮ㅎ????frontend
npm install
npm run dev
```

Browser URLs:

```text
http://localhost:5173/analyze
http://localhost:5173/law-updates
```

Use `as_of = 2099-06-15` on the analysis screen to show the current TEST version and scheduled TEST version metadata. The law updates screen should show a TEST event with `impacted_step_codes`.

Detailed manual checklist:

```text
docs/manual_test_phase9.md
```

The frontend remains a local npm workflow in Phase 9. Docker Compose frontend service is still deferred to keep the backend/database verification path stable.

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

- Do not determine whether an assessment is required in Phase 9.
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
git commit -m "Add phase 9 local demo testing flow"
git status
```

## Phase 9.5 Korean Dashboard UX

Phase 9.5 improves the React MVP so that local browser testing is easier for Korean users. It is a frontend UI/UX cleanup phase only. Backend API response shapes and `analysis_results.result_payload` storage remain unchanged.

Main UI changes:

```text
Korean navigation labels and active menu state
Dashboard cards for analysis, law update events, development status, and local test guidance
Korean form labels, help text, loading messages, empty states, and error messages
Analysis result summary, procedure table, and legal-reference cards
Law update event table with Korean labels and status text
Raw API response hidden under a developer-only expandable section
```

Common frontend label helpers were added under:

```text
frontend/src/utils/labels.ts
frontend/src/utils/formatters.ts
```

The UI still displays only backend-provided metadata such as IDs, keys, status, effective date, and source. It does not invent real law names, article numbers, or legal criteria. TEST_*_DO_NOT_USE data remains development-only.

Manual browser checklist:

```text
docs/manual_test_phase9_5.md
```

The frontend remains a local npm workflow. Run the backend, apply migrations, seed demo data, and then start Vite:

```powershell
docker compose up --build --detach
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.dev_seed
cd frontend
npm install
npm run dev
```

Real MOLEG data integration, RAG, production UI workflows, real legal article mapping, and final criteria remain later-phase work.

## Phase 10 Analysis History UI

Phase 10 connects the existing backend analysis history APIs to the React frontend. It does not change backend response shapes or `analysis_results.result_payload` storage.

Added browser screens:

```text
/analyses              Analysis history list
/analyses/:analysisId  Stored analysis detail
```

The analysis history list calls `GET /api/analyses` and then reads each visible item through `GET /api/analyses/{analysis_id}` to calculate display-only counts such as procedure count and legal-reference count. This keeps the backend API unchanged.

The analysis detail screen reuses the same `AnalysisResult` component used by the `/analyze` screen. Stored `result_payload` is displayed as analysis summary, procedure list, and step-level legal references. Raw JSON remains hidden inside developer-only expandable sections.

The dashboard now includes a recent analysis history section. It shows recent stored analyses and links to the full history list. If the recent-history API request fails, the dashboard keeps rendering the other cards and shows a separate Korean error message for that section only.

Manual browser checklist:

```text
docs/manual_test_phase10.md
```

Browser test flow:

```powershell
docker compose up --build --detach
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.dev_seed
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:5173/analyze
http://localhost:5173/analyses
http://localhost:5173/analyses/{analysisId}
```

Phase 10 continues the existing placeholder policy. It does not add real law names, real article numbers, final legal criteria, MOLEG network calls, or RAG.

## Phase 11 Procedure Roadmap UI

Phase 11 improves the analysis result display with a procedure roadmap and step detail UI. It does not change backend API response shapes or `analysis_results.result_payload` storage.

Added frontend components:

```text
frontend/src/components/ProcedureRoadmap.tsx
frontend/src/components/ProcedureStepDetail.tsx
```

The roadmap displays backend-provided procedure steps in sequence. Each step shows the step number, name, description, step code, legal-reference count, required documents, related agencies, and estimated duration. The step detail panel shows legal references, required documents, related agencies, duration, and notes with Korean empty states when data is missing.

The same `AnalysisResult` component is still used by both screens:

```text
/analyze
/analyses/:analysisId
```

This means immediate analysis results and stored analysis details share the same roadmap UI. Raw JSON remains hidden under developer-only expandable sections.

Manual browser checklist:

```text
docs/manual_test_phase11.md
```

Phase 11 continues the existing placeholder policy. It does not add real law names, real article numbers, final legal criteria, MOLEG network calls, or RAG.

## Phase 12 Procedure Checklist UI

Phase 12 adds a frontend-only checklist UI to each procedure step in the roadmap. It does not add authentication, server persistence, database migrations, backend API changes, or changes to `analysis_results.result_payload`.

Checklist items are generated only from the existing analysis response categories:

```text
Legal reference check
Required documents check
Related agencies check
Estimated duration check
Notes and cautions check
```

The UI displays these as Korean work-check items and shows Korean empty states when the response has no data, such as no connected legal references or no registered required documents.

Step status is managed in React state for the current screen only:

```text
亦껋꼶梨????筌먦끉逾ι쨹??筌먦끉逾?熬곣뫁??```

Refreshing the browser resets checklist state in Phase 12. The same roadmap and checklist UI appears in both immediate analysis results and stored analysis details:

```text
/analyze
/analyses/:analysisId
```

Manual browser checklist:

```text
docs/manual_test_phase12.md
```

Phase 12 continues the existing placeholder policy. It does not add real law names, real article numbers, final legal criteria, MOLEG network calls, or RAG.

## Phase 13 Analysis Report Print View

Phase 13 adds a report-style summary section to analysis results. It does not add server-side PDF generation, file download APIs, authentication, database migrations, backend API changes, or changes to `analysis_results.result_payload`.

The report section appears in both analysis result surfaces:

```text
/analyze
/analyses/:analysisId
```

The report displays backend-provided and screen-state data in a structured format:

```text
Report title
Project name or project ID
Analysis ID when available
as_of date
created_at when available
Analysis summary
Procedure step count
Legal reference count
Procedure roadmap summary
Step detail summary
Step-level legal reference count
Checklist status summary from the current browser screen
Development TEST data notice
Reference disclaimer
```

The `?紐꾨뇵??띾┛` button calls `window.print()`. Users can use the browser print dialog to print or save as PDF. Print-specific CSS hides navigation, buttons, input forms, and developer raw JSON sections so the report is easier to read on paper or in browser-generated PDFs.

Manual browser checklist:

```text
docs/manual_test_phase13.md
```

Phase 13 continues the existing placeholder policy. It does not add real law names, real article numbers, final legal criteria, MOLEG network calls, or RAG.

## Phase 14 Analysis Result Data Consistency

Phase 14 improves how the frontend interprets and displays `result_payload` data. It does not change backend API response shapes, database schema, migrations, or `analysis_results.result_payload` storage.

A shared normalization utility was added:

```text
frontend/src/utils/analysisSummary.ts
```

The utility derives stable display values for project summary, procedure counts, legal-reference counts, missing-reference counts, checklist status counts, step titles, descriptions, legal references, required documents, related agencies, estimated duration, status, and missing-data indicators.

Data missing display policy:

```text
No legal reference -> 洹쇨굅 誘몄뿰寃?No agency -> 湲곌? ?뺤씤 ?꾩슂
No required document -> ?쒕쪟 ?뺤씤 ?꾩슂
No duration or TODO duration -> 湲곌컙 ?뺤씤 ?꾩슂
No status -> 誘명솗??```

The procedure roadmap and report view now use the same normalized summary data so missing data is displayed consistently. The report also shows a clearer reference notice:

```text
蹂?遺꾩꽍 寃곌낵???꾩떆媛쒕컻?ъ뾽 ?덉감 寃?좊? ?꾪븳 李멸퀬?먮즺?대ŉ, 理쒖쥌 ?곸슜 ?щ???愿怨?踰뺣졊 ?먮Ц, ?명뿀媛沅뚯옄 ?묒쓽 諛??꾨Ц媛 寃?좊? ?듯빐 ?뺤씤?댁빞 ?⑸땲??
```

Phase 14 does not invent law names, article numbers, agencies, documents, or legal criteria. It only displays values already present in stored/backend response data, or explicit Korean missing-data states.

Manual browser checklist:

```text
docs/manual_test_phase14.md
```

Server PDF generation remains unimplemented. Browser print/PDF output from Phase 13 remains the current print path.

## Phase 15 Final QA and Release Readiness

Phase 15는 현재 로컬 MVP의 최종 QA와 릴리즈 준비 상태를 점검하는 단계입니다. 백엔드 API, DB schema, Alembic migration, 서버 PDF 생성, 인증, RAG, 실제 법제처 네트워크 연동은 추가하지 않았습니다.

로컬 실행 가이드:

```powershell
docker compose up --build --detach
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.dev_seed
docker compose exec backend pytest

cd frontend
npm install
npm run typecheck
npm run build
npm run dev
```

주요 화면 URL:

```text
http://localhost:5173/
http://localhost:5173/analyze
http://localhost:5173/analyses
http://localhost:5173/analyses/{analysisId}
http://localhost:5173/law-updates
```

브라우저 인쇄/PDF 저장 방법:

```text
1. 신규 분석 결과 또는 저장 분석 상세 화면을 엽니다.
2. 보고서형 요약 섹션을 확인합니다.
3. 화면의 인쇄 버튼 또는 브라우저 인쇄 기능을 사용합니다.
4. 필요한 경우 브라우저 인쇄 대화상자에서 PDF로 저장합니다.
```

서버에서 PDF 파일을 생성하는 API는 아직 구현하지 않았습니다. 현재 출력 방식은 브라우저 인쇄/PDF 저장입니다.

현재 제공하는 주요 기능:

```text
React 화면에서 사업 분석 요청
저장된 분석 이력 목록 및 상세 조회
절차 로드맵과 단계 상세 표시
프론트엔드 화면 상태 기반 단계별 체크리스트
보고서형 요약 및 브라우저 인쇄/PDF 보기
TEST 데이터 기반 법령 근거 연결 데모
개발 검증용 법령 개정 감지 내역 표시
```

최종 QA 범위:

```text
대시보드
신규 분석 실행 흐름
저장 분석 목록
저장 분석 상세
없는 분석 ID 처리
법령 개정 감지 화면
브라우저 인쇄/PDF 출력
좁은 화면 레이아웃 기본 점검
raw JSON은 개발자용 상세 영역에만 표시되는지 확인
```

데이터 및 법적 한계:

```text
이 프로그램은 도시개발사업 절차 검토를 위한 참고자료입니다.
법적 유권해석, 법률 의견, 최종 인허가 판단을 대체하지 않습니다.
최종 적용 여부는 관계 법령 원문, 인허가권자 협의 및 전문가 검토를 통해 확인해야 합니다.
실제 법령 조문 데이터셋, 지자체 조례, 판단 기준은 후속 검증과 보강이 필요합니다.
```

문제 발생 시 확인 항목:

```text
백엔드 서버가 http://localhost:8000 에서 실행 중인지 확인
프론트엔드 Vite 서버가 http://localhost:5173 에서 실행 중인지 확인
DB migration이 적용되었는지 확인
TEST 데이터가 필요하면 demo seed가 실행되었는지 확인
npm typecheck/build 실패가 없는지 확인
```

다음 고도화 후보:

```text
실제 도시개발법/시행령/시행규칙 조문 데이터셋 보강
심의/평가 대상 판별 규칙 고도화
지자체 조례 연동
서버 PDF 생성 API
사용자별 체크리스트 상태 저장
배포 환경 구성
```

최종 수동 QA 문서:

```text
docs/manual_test_phase15.md
```
## v0.1 MVP Release Documents

현재 버전은 v0.1 MVP로, 도시개발사업 절차 분석 흐름을 시연하기 위한 로컬 실행용 버전입니다. 실제 인허가 판단에는 관계 법령 원문, 인허가권자 협의 및 전문가 검토가 필요합니다.

```text
docs/release_notes_v0.1.md
docs/final_feature_summary.md
docs/known_limitations.md
docs/manual_test_phase15.md
docs/manual_test_phase16.md
```
## Phase 17 Legal Data Coverage

Phase 17 starts the first legal-data coverage improvement after the v0.1 MVP release tag. It focuses on procedure and legal-reference data quality, not new screens or schema changes.

Status:

```text
v0.1-mvp tag: already created
Existing API compatibility: maintained
DB migration: not added
Server PDF generation API: still not implemented
Automatic legal original-text collection: still not implemented
Raw JSON policy: developer detail section only
```

Phase 17 adds a common placeholder procedure step for implementer designation review:

```text
IMPLEMENTER_DESIGNATION_REVIEW
```

This step improves core workflow coverage but intentionally keeps documents, agencies, duration, and legal article references as confirmation-required values. No actual law name, article number, agency, document, or criteria was invented.

Data missing display policy remains:

```text
근거 미연결
기관 확인 필요
서류 확인 필요
기간 확인 필요
미확인
링크 확인 필요
```

Coverage and manual verification documents:

```text
docs/legal_data_coverage_phase17.md
docs/manual_test_phase17.md
```

Next enhancement candidates:

```text
Official legal article mapping after source verification
Verified article titles and article URLs
Jurisdiction-specific ordinance mapping
Validated required documents and agency lists
Reviewed duration ranges
Additional confirmed legal references per step
```
## Phase 18 Core Legal Reference Coverage

Phase 18 expands TEST legal reference candidate coverage for the 11 core common procedure steps. It does not finalize actual law names, article numbers, article titles, agencies, required documents, criteria, or URLs.

Core common procedure recheck result:

```text
Core common procedure candidates: 11
TEST candidate legal reference connected core steps: 11
Verified legal mappings: 0
Verification-required candidate mappings: 11
DB migration: not added
Existing API compatibility: maintained
Server PDF generation API: still not implemented
Automatic legal original-text collection: still not implemented
```

Verification status policy:

```text
검증 완료: official source and expert review completed; not used in Phase 18
후보 연결: TEST legal reference connected for coverage verification
검증 필요: official source, article, ordinance, agency, document, and expert validation required
근거 미연결: no legal reference connected
```

The demo seed now connects TEST-only legal reference candidates to all core common steps. Method-specific and implementer-specific branch steps may still remain `근거 미연결` until separately verified. The `/law-updates` TEST event remains focused on `PROJECT_BASIC_REVIEW`.

Documents:

```text
docs/legal_data_coverage_phase18.md
docs/manual_test_phase18.md
```

Next enhancement candidates:

```text
Official article mapping for urban development statutes after source verification
Verified article titles and article URLs
Validated document and agency datasets
Local ordinance mapping
Reviewed duration guidance
Expert review before any 검증 완료 status is used
```
## Phase 19 Legal Reference Quality

Phase 19 adds legal reference quality status so candidate TEST references are not mistaken for verified legal grounds.

Quality states:

```text
candidate -> 후보근거
verified -> 검증완료
missing -> 근거미확인
```

API additions keep existing fields and add supplemental fields:

```text
procedures[].legal_reference_status
procedures[].legal_references[].reference_quality
```

Current Phase 18 demo seed references for the 11 core common procedure steps are displayed as `candidate`. Steps without references are displayed as `missing`. Phase 19 does not mark any reference as `verified` and does not add MOLEG network calls, external data fetching, DB migrations, server PDF generation, or actual law article finalization.

Candidate-reference notice shown in the UI/report/browser print-PDF path:

```text
본 법령 근거는 현재 후보 데이터 기준으로 연결된 항목이며, 공식 법령 원문 및 인허가권자 확인이 필요합니다.
```

PDF/print verification scope:

```text
Phase 19 updates the browser print/PDF report component so reference quality status and the candidate-reference notice are included in the printable report layout.
Actual PDF file saving is still a manual browser print-environment check. No automated PDF file generation or server-side PDF API was added.
```

Detailed quality policy:

```text
docs/legal_reference_quality_phase19.md
```