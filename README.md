# Urban Development Analysis Program

This project analyzes general urban development projects with a FastAPI backend, PostgreSQL persistence, and YAML-based rule files.

Current stage: Phase 1.

Phase 1 adds PostgreSQL persistence for analysis requests and results. MOLEG Open API and RAG are not integrated yet.

## Important Limits

- This application is not a final legal determination tool.
- Legal article numbers are not finalized.
- Environmental impact assessment, traffic impact assessment, underground safety assessment, and buried cultural heritage review thresholds remain TODO/placeholders.
- Real criteria must be finalized later through MOLEG Open API integration and expert review.

## Windows PowerShell Local Run

```powershell
cd C:\Users\poiu2\Desktop\??????_??_??_????
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For local backend execution outside Docker, use `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/urban_dev` while the Compose PostgreSQL container is running.

## Docker Compose Run

Start Docker Desktop first, then run from the project root.

```powershell
cd C:\Users\poiu2\Desktop\??????_??_??_????
docker compose up --build
```

Detached mode:

```powershell
docker compose up --build --detach
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

The host/local PostgreSQL port is mapped to `5433` to avoid conflicts with an existing local PostgreSQL on `5432`.

```text
host: localhost
port: 5433
database: urban_dev
user: postgres
password: postgres
```

Tables are created automatically at FastAPI startup for Phase 1. A future phase should replace this with Alembic migrations.

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

The response keeps the Phase 0 analysis fields and also includes persistence metadata:

```text
project_id
analysis_id
created_at
```

### List Stored Analyses

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/analyses" -Method Get | ConvertTo-Json -Depth 5
```

### Get Stored Analysis Detail

```powershell
$analysisId = $result.analysis_id
Invoke-RestMethod -Uri "http://localhost:8000/api/analyses/$analysisId" -Method Get | ConvertTo-Json -Depth 8
```

## Assessment Response Policy

- Do not determine whether an assessment is required in Phase 1.
- Keep thresholds as `TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA`.
- Mark assessment status as legal review required.
- Finalize criteria later through MOLEG Open API and expert review.

## Tests

```powershell
cd C:\Users\poiu2\Desktop\??????_??_??_????
python -m pytest
```

The persistence tests require PostgreSQL to be running. The recommended setup is:

```powershell
docker compose up --build --detach
python -m pytest
```

## Git Commit

```powershell
git status
git add .
git commit -m "Add database persistence for analysis results"
git status
```
