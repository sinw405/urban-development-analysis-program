# Phase25: Official Law DB Snapshot Source

## Purpose

Phase25 connects the normalized official law tables created in Phase24 to the legal reference verification flow. The goal is to make stored `official_law_documents` and `official_law_articles` the first source of evidence before attempting live MOLEG calls or mock fallback.

This phase does not decide legal reference values manually and does not hard-code article numbers. It only connects persisted official-law snapshots to the existing preview workflow.

## Source Resolution Order

The verification preview now resolves official law evidence in this order:

1. `official_db`: query stored `official_law_documents` and `official_law_articles`.
2. `live`: call the configured MOLEG adapter only when requested and only after no usable DB snapshot is found.
3. `fallback`: use the mock provider when live lookup is unavailable, errors, or has no usable result.
4. `mock`: existing mock behavior when no live attempt was requested.

When an official DB snapshot matches, live connectivity is not required for the endpoint to succeed.

## Why Live Connection Errors Are Not Blockers

Phase23 and Phase24 already confirmed that local configuration can detect `MOLEG_API_ENABLED` and whether a secret exists without exposing the secret value. The remaining live issue is a connectivity/provider response problem represented as `connection_error` or another sanitized `source_error` reason.

Phase25 is about using persisted official-law snapshots. Therefore a live `connection_error` is not a blocker when a DB snapshot is available. If the snapshot is absent and live fails, the endpoint keeps returning a safe preview response using fallback/mock behavior.

## Official DB Snapshot Role

`official_law_documents` stores normalized law-level metadata such as law title, law ID, MST, enforcement date, current status, document status, normalized timestamp, provider reason, and sanitized source URL.

`official_law_articles` stores normalized article-level evidence connected to a document. The DB source provider returns article snapshots with:

- `source_mode`: `official_db`
- `document_id` / `official_document_id`
- `article_count`
- `evidence_type`: `official_law_documents_snapshot`
- `source_hint`

The snapshot is used as verification evidence, not as a final legal conclusion by itself.

## Snapshot Diagnostic API

`GET /api/legal-references/official-law-snapshot` returns aggregate snapshot state:

- `document_count`
- `article_count`
- `ingest_run_count`
- `latest_ingest_status`
- `source_provider`
- `last_normalized_at`
- `has_current_documents`

This endpoint does not return raw live payloads or any API credentials.

## Security Policy

- MOLEG API keys are read only from environment variables.
- `.env`, `.env.local`, and `*.env.local` remain uncommitted.
- Raw live payloads are not stored in full.
- Evidence rows store sanitized summaries only.
- Request URLs, OC/API keys, headers, and other secret-bearing values must not be logged, returned by API responses, or committed.

## Phase26 Follow-up

Phase26 should focus on live connectivity diagnostics and provider behavior:

- distinguish DNS, TLS, timeout, HTTP status, authentication, and parse failures more precisely;
- confirm MOLEG endpoint accessibility from the runtime environment;
- validate real response shapes once connectivity succeeds;
- decide whether DB snapshots should be refreshed by a controlled batch job;
- add operator-facing diagnostics without exposing secrets.
