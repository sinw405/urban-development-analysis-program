# Deployment baseline

Development:

    docker compose -f compose.dev.yml config
    docker compose -f compose.dev.yml build
    docker compose -f compose.dev.yml up -d
    Invoke-RestMethod http://localhost:8000/health
    docker compose -f compose.dev.yml down

Production-like:

    Copy-Item production.env.example .env.production
    # Replace all placeholders in .env.production.
    docker compose --env-file .env.production -f compose.prod.yml config
    docker compose --env-file .env.production -f compose.prod.yml build
    docker compose --env-file .env.production -f compose.prod.yml up -d
    docker compose --env-file .env.production -f compose.prod.yml logs migrate
    docker compose --env-file .env.production -f compose.prod.yml exec backend alembic current
    Invoke-WebRequest http://localhost:8080/healthz
    docker compose --env-file .env.production -f compose.prod.yml down

Migration waits for PostgreSQL health. No seed runs automatically. Production rejects debug, fixture, auto-seed, local database, and placeholder-secret settings. Do not use down -v unless deleting the database volume is intended. No external production target is configured.

## Monitoring and logging

The backend writes one JSON object per operational event to stdout. Stable fields include `timestamp`, `level`, `event`, `component`, and, during an HTTP request, `correlation_id`. HTTP completion events also contain method, path, status, duration, and an error category. The server accepts a safe `X-Request-ID` (ASCII letters, digits, `.`, `_`, or `-`, maximum 128 characters), generates one otherwise, and returns it in the response header.

Use `docker compose ... logs backend` and filter by these event names:

* `http.request.completed`: normal, client-error, or server-error response
* `http.request.validation_error`: request validation failure (422)
* `http.request.expected_error`: handled HTTP 4xx/5xx
* `http.request.unhandled_exception`: unexpected exception
* `law.collection.failed`: scheduler collection failure and retry count
* `law.amendment.evaluated`: amendment/diff result and changed article count
* `operational.alert`: alert abstraction; `destination=structured_log` is the default fallback

Request bodies and query strings are not logged. Structured fields and exception text redact database URL passwords, `POSTGRES_PASSWORD`, Authorization/Bearer values, API keys, access/refresh tokens, passwords, secrets, and credentials. Do not put secrets in law identifiers or other business identifiers. No external alert SaaS is configured or required.

## PostgreSQL backup and isolated restore validation

The `operations` profile contains one-shot jobs; it does not add a long-running service. From the repository root:

    New-Item -ItemType Directory -Force backups | Out-Null
    docker compose -f compose.dev.yml --profile operations run --rm db-backup
    docker compose -f compose.dev.yml --profile operations run --rm db-restore-validate

For production-like configuration, use the external secret environment file without printing it:

    docker compose --env-file .env.production -f compose.prod.yml --profile operations run --rm db-backup
    docker compose --env-file .env.production -f compose.prod.yml --profile operations run --rm db-restore-validate

Successful artifacts are custom-format logical dumps at `backups/urban_dev_YYYYMMDD_HHMMSS_microsecondsZ.dump`. A dump is first written as `.partial`, checked as non-empty, and atomically renamed. Failure exits non-zero and removes the partial artifact. The `backups/` directory is Git-ignored.

Restore validation selects the newest valid timestamped artifact unless `--artifact` is supplied. It creates a uniquely named `phase60_restore_validation_*` database, restores with `pg_restore --exit-on-error`, and drops only that disposable database afterward. It never drops, cleans, or overwrites the configured application database. Never use `docker compose down -v` as part of backup validation, and never point an ad-hoc restore command at production.

For PostgreSQL 17 client dumps restored to PostgreSQL 16, the initial `SET transaction_timeout = 0;` can fail because the server does not support that setting. Only that exact failure triggers a retry: render the archive as SQL, omit the first exact setting line, and execute it with `psql -X --set ON_ERROR_STOP=1` against the same disposable database. Temporary SQL files are removed afterward. A final `current_database()` query verifies connection to the validation database; this is not a full application data integrity check. Failure diagnostics include the stage, sanitized command, return code, stderr and stdout. Cleanup failure is reported separately and does not mask an earlier restore failure.

After code changes, rebuild the validation image before host revalidation:

    docker compose -f compose.dev.yml --profile operations build db-restore-validate
    docker compose -f compose.dev.yml --profile operations run --rm db-restore-validate
    $LASTEXITCODE
