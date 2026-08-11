# Phase 44 Law Update Scheduler and Monitoring

## Purpose

Phase 44 schedules the Phase 43 live law-change pipeline and records batch and per-law outcomes. It does not duplicate discovery, ingest, diff, impact, event, audit, or idempotency logic. The React notification UI is deferred to Phase 45.

## Architecture

FastAPI lifespan starts an APScheduler `BackgroundScheduler` only when explicitly enabled. Its single interval job calls `run_law_update_batch("scheduled")`. The manual API and local smoke runner call the same batch service. Each enabled registry row is processed independently through `analyze_live_law_change(..., ensure_versions=True, persist_event=True)`.

## Configuration

- `LAW_UPDATE_SCHEDULER_ENABLED`: default `false`; no thread starts on import or in tests.
- `LAW_UPDATE_SCHEDULER_INTERVAL_HOURS`: default `24`, must be greater than zero.
- `LAW_UPDATE_SCHEDULER_RETRY_COUNT`: default `1`, allowed range `0..2`.
- `LAW_UPDATE_SCHEDULER_RETRY_BACKOFF_SECONDS`: default `0.25`, must be non-negative.

The existing MOLEG base URL, credential, timeout, and retry-aware client remain authoritative.

## Registry

`law_update_registry` stores an extensible set of `law_identifier`, `law_name`, `enabled`, `priority`, `last_checked_at`, `last_success_at`, and `last_detected_mst`. No target law is seeded or hardcoded. The local smoke runner registers the operator-supplied `--law-name`.

## Batch flow and persistence

A `law_update_runs` row records trigger, status, counts, timestamps, duration, and sanitized error. A `law_update_run_items` row records each target's selected MSTs, version/content state, event reference, retry count, duration, and sanitized failure. One failed law does not stop later laws.

## Retry and timeout

The scheduler reuses `MolegLiveClient` and its finite HTTP timeout. Only timeout, transient connection/proxy/DNS, and HTTP transport errors are retried. Authentication, validation, parser, and business errors are not. Backoff is exponential and bounded by the configured retry count.

## Concurrency

APScheduler uses `max_instances=1` and `coalesce=True`. PostgreSQL session advisory locks independently protect the whole batch and each normalized law identifier, including manual/scheduled overlap and multiple API processes.

## Lifecycle

FastAPI lifespan starts the scheduler when enabled and shuts it down gracefully. Importing `app.main` alone never starts a scheduler. Duplicate registration is ignored.

## API

- `POST /api/law-updates/scheduler/run`: one manual batch.
- `GET /api/law-updates/scheduler/status`: enabled/running, last run/success, next run, latest status.
- `GET /api/law-updates/runs?limit=20`: recent batch history.
- `GET /api/law-updates/runs/{run_id}`: batch and law-item details.

## Logging and security

Logs contain run ID, law name, status, elapsed time, retry count, and event ID only. API keys, `.env` values, credential query strings, full request URLs, raw payloads, and full law text are neither logged nor stored. Errors are sanitized and truncated.

## Migration

Run Alembic from the project root:

```powershell
python -m alembic -c .\alembic.ini upgrade head
python -m alembic -c .\alembic.ini current
```

## Local Live Smoke

Run only from the user's Windows VS Code PowerShell after Phase 43 Local Live Acceptance:

```powershell
python -m scripts.phase44_local_live_smoke --law-name "도시개발법"
```

The runner registers/enables the supplied law, manually executes one shared scheduler batch, reads its run item, and prints `PASS` or a sanitized failure category.

## Known limits

APScheduler jobs are process-local, while PostgreSQL locks provide cross-process execution protection. Registry management currently uses DB administration or the smoke runner; a dedicated operator UI is deferred. External MOLEG availability remains outside the Codex gate.

## Phase 45

Phase 45 may add a React monitoring and notification UI over the status and history APIs. RAG is not part of Phase 44.