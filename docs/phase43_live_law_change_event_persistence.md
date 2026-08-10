# Phase 43 — Live law version ingest and change-event persistence

## Purpose

Phase 43 extends `POST /api/law-updates/live-impact` from discovery-only behavior into a complete MOLEG workflow: discover or validate a version pair, verify both stored documents, ingest missing details from the real MOLEG API, diff normalized articles, resolve existing procedure mappings, and persist one idempotent aggregate event with an audit trail.

No scheduler, UI, RAG, LLM explanation, raw API payload, credential, or full secret-bearing URL is added.

## Data flow

1. Discover every eflaw search page and select or validate the MST pair.
2. Query `official_law_documents` by exact law title and MST.
3. Treat a document as complete only when its status is `normalized`, it has at least one `official_law_article`, and every article has non-empty text.
4. Fetch only incomplete MSTs through the existing MOLEG detail client and parser.
5. Reuse `sync_official_document()` and `_sync_law_tables()` for transactional, idempotent persistence.
6. Re-check stored article counts and completeness.
7. Reuse `LawVersionImpactService` and its whitespace-normalized article diff.
8. Persist one `live_law_change_events` row and ordered `live_law_change_event_audits` rows.

A metadata-only or empty-article document is not considered complete. API and parse failures produce `ingest_failed`; no mock result is substituted.

## Diff and status semantics

The existing diff compares stable article identity, title, and normalized text. Repeated whitespace and line-break-only differences are ignored. Public change types are `added`, `removed`, `modified`, and unchanged articles are counted internally but omitted from `changed_articles`.

- `version_changed`: the selected MST values differ.
- `content_changed`: at least one normalized article was added, removed, or modified.
- Legacy `changed`: retained for compatibility and now follows `content_changed` when Phase 43 runs.

`analysis_status` values:

- `completed`: article content changed and analysis completed.
- `no_change`: both versions were analyzed and no normalized content changed.
- `missing_version`: automatic ingest was disabled and a complete version was unavailable.
- `ingest_failed`: detail retrieval, parsing, persistence, or completeness verification failed.
- `analysis_failed`: both documents existed but diff or impact analysis failed.

## Event storage and idempotency

`live_law_change_events` stores one aggregate comparison. Changed articles and mapped rule impacts are stored as sanitized JSON summaries; Phase 40's existing `law_change_impact_events` remains the article-level review structure.

The SHA-256 idempotency key is based on normalized `source + law identifier + from_mst + to_mst`. A unique constraint protects concurrent requests. On an integrity race the transaction is rolled back and the winning existing row is returned. Repeated requests reuse the event; `force_reanalyze=true` refreshes results.

Audit actions are `discovered`, `ingest_started`, `ingest_completed`, `analysis_started`, `analysis_completed`, `analysis_failed`, and `persisted`. Audit detail contains only identifiers, counts, status, and sanitized error codes.

## Rule impacts

The existing confirmed or candidate procedure mapping is reused. Each mapped result contains `rule_type`, `rule_id`, `rule_name`, `related_article`, `impact_reason`, and `review_required`. No mapping is invented. `changed_articles_have_no_rule_mapping` distinguishes changed-but-unmapped from `no_content_change`.

## API

```http
POST /api/law-updates/live-impact
Content-Type: application/json
```

```json
{
  "law_name": "도시개발법",
  "ensure_versions": true,
  "persist_event": true,
  "force_reanalyze": false
}
```

Manual `from_mst` and `to_mst` remain supported and are validated by Phase 42 rules.

```json
{
  "law_name": "도시개발법",
  "source": "MOLEG",
  "selection_mode": "auto",
  "version_changed": true,
  "content_changed": true,
  "analysis_status": "completed",
  "changed": true,
  "changed_articles": [],
  "impacted_rules": [],
  "event": {"id": 1, "idempotency_key": "<sha256>", "created": true},
  "warnings": [],
  "errors": [],
  "secret_exposed": false
}
```

## Tests and live verification

```powershell
python -m pytest tests/test_phase41_live_law_change_e2e.py -q
python -m pytest tests/test_phase42_law_version_discovery_api.py -q
python -m pytest tests/test_phase43_live_law_change_persistence.py -q
python -m pytest -q
alembic upgrade head
```

Live verification requires local `.env` values such as `MOLEG_API_ENABLED=true`, `MOLEG_LIVE_TEST_ENABLED=true`, `MOLEG_API_BASE_URL`, and `MOLEG_API_KEY` or `MOLEG_OC`. Never print or commit their values. The normal pytest suite does not require live network access.

## Security and known limits

Only actual normalized MOLEG responses are stored. Raw payloads, API keys, full request URLs, and full law text are excluded from event and audit records. Rule impacts are limited to mappings already represented by the current procedure candidate model; assessment-rule-specific relationships require a future normalized cross-reference model.

The next phase may add operator review endpoints and scheduled checks without changing the Phase 43 idempotency contract.
