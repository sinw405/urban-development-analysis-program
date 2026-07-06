# Urban Development Analysis Program

This project analyzes general urban development projects with a FastAPI backend, PostgreSQL persistence, Alembic migrations, and YAML-based rule files.

Current stage: Phase 1.5.

Phase 1.5 keeps the Phase 1 PostgreSQL storage and lookup base, then adds Alembic migrations and paginated analysis lookup. MOLEG Open API and RAG are not integrated yet.

## Important Limits

- This application is not a final legal determination tool.
- Legal article numbers are not finalized.
- Environmental impact assessment, traffic impact assessment, underground safety assessment, and buried cultural heritage review thresholds remain TODO/placeholders.
- Assessment thresholds must remain `TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA` until later legal review.
- Real criteria must be finalized later through MOLEG Open API integration and expert review.

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

## Assessment Response Policy

- Do not determine whether an assessment is required in Phase 1.5.
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
git commit -m "Add migrations and paginated analysis queries"
git status
```
