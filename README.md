# Urban Development Analysis Program

This project is a Phase 0 / S0 MVP for analyzing general urban development projects.

The current MVP provides a FastAPI backend, YAML-based procedure rules, placeholder assessment rules, and Docker Compose for backend + PostgreSQL.

## Important Limits

- This MVP is not a final legal determination.
- Legal article numbers are not finalized.
- Environmental impact assessment, traffic impact assessment, underground safety assessment, and buried cultural heritage review thresholds are TODO/placeholders.
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

## PostgreSQL Ports

The backend container connects to PostgreSQL through Docker internal networking:

```text
postgres:5432
```

The host/local PostgreSQL port is mapped to `5433` to avoid conflicts with an existing local PostgreSQL on `5432`.

```text
host: localhost
port: 5433
database: urban_dev
user: postgres
password: postgres
```

## API Tests

In Windows PowerShell, `curl` can resolve to an `Invoke-WebRequest` alias. Use `curl.exe` for these checks.

### Health

```powershell
curl.exe http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

### Analyze

Use `ConvertTo-Json` to avoid JSON quoting problems in PowerShell.

```powershell
$body = @{
  project_name = "Test Urban Development Project"
  location = "Seongnam-si, Gyeonggi-do"
  area_square_meters = 100000
  implementation_method = "Expropriation or use method"
  implementer_type = "Local public corporation"
  local_government = "Seongnam-si"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8000/api/analyze" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 8
```

The response includes project input, procedure steps from `rules/procedure_rules.yaml`, assessment placeholders from `rules/assessment_rules.yaml`, and warnings.

Assessment response policy:

- Do not determine whether an assessment is required in Phase 0.
- Keep thresholds as `TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA`.
- Mark assessment status as legal review required.
- Finalize criteria later through MOLEG Open API and expert review.

## Tests

```powershell
cd C:\Users\poiu2\Desktop\??????_??_??_????
python -m pytest
```

## Initial Git Commit

```powershell
git status
git add .
git commit -m "Initial MVP skeleton for urban development analysis"
git status
```
