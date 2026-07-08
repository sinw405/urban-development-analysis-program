# Phase 24 Official Law Document Persistence

## Purpose

Phase 24 adds persistence for normalized official law documents prepared in Phase 23. It also adds a safe MOLEG diagnostic path so live `source_error` cases can be classified without exposing API keys.

## Phase 23 Source Error Interpretation

`live_configured=true` means the application can see live mode, base URL, and a secret value in the environment. It does not prove that the key is valid or that the network path to law.go.kr is reachable.

A live `source_error` means the provider attempted the source and failed due to timeout, connection error, HTTP error, parsing error, auth error, or another source failure.

## Diagnostic

Endpoint:

```text
GET /api/legal-references/official-laws/diagnostic
```

The response exposes only safe fields:

```text
live_configured
has_secret
base_url
endpoint
result
reason_type
secret_exposed=false
```

`reason_type` is one of:

```text
timeout
connection_error
http_error
parse_error
auth_error
disabled
unknown
ok
```

## DB Tables

Phase 24 adds:

```text
official_law_documents
official_law_articles
official_law_ingest_runs
official_law_source_evidence
```

`official_law_documents` stores normalized law document metadata, including provider, source mode, law title, short title, law id, MST, promulgation date, enforcement date, current flag, document status, normalized time, provider reason, and sanitized source URL.

`official_law_articles` stores normalized article units for each document, including article number, title, text, paragraph JSON, source anchor, hint, and sort order.

`official_law_ingest_runs` records fixture/live ingest attempts, selected candidate identifiers, candidate count, article count, status, and source error reason.

`official_law_source_evidence` stores sanitized summary evidence only. It does not store raw live payloads or query-string URLs.

## Versioning Policy

The Phase 24 document identity is:

```text
source_provider + law_id + mst + enforcement_date
```

This is enforced through a unique constraint. If the same normalized document is saved again, the document row is updated and article rows are replaced, preventing duplicate growth.

## Index Policy

Indexes are added for:

```text
law_title
law_id
mst
enforcement_date
is_current
document_status
article document_id
article_no
ingest status/query/source_mode/started_at
evidence ingest_run_id/evidence_type
```

## Raw Payload Policy

Full raw payloads are not persisted. Only sanitized summary evidence and limited redacted debug samples may be used in memory. `OC`, API key values, query-string request URLs, and headers are not persisted.

## Fixture, Mock, And Live Ingest

Fixture ingest is used by tests and can persist normalized document and articles without network access.

Mock mode remains the default for verify-preview and does not write official law documents.

Live ingest preview can be requested through service/API, but failures are recorded as `source_unavailable` or `source_error` without failing the app.

## Verify Preview Relationship

`verify-preview` remains an immediate verification preview path. `official_law_documents` is the future evidence store. Phase 25 can make verify-preview prefer DB snapshots first, then use live fallback only when explicitly requested.

## Current Limits

Phase 24 does not run a full legal collection batch. It does not promote candidates to verified. It does not persist full raw official payloads.

## Phase 25 Tasks

Phase 25 should add controlled collection for ?????, ???, and ????, persist normalized official documents, and wire verify-preview to prefer stored DB snapshots before live calls.
