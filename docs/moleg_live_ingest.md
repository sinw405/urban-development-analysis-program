# MOLEG Live Ingest

## Purpose

Phase 37 adds a controlled live ingest path for official MOLEG data after Phase 36.1 confirmed browser-compatible transport. The initial supported target is one law per run, with `도시개발법` used for the first live import.

This ingest path does not create legal-basis mappings by itself. It stores official law/article data and provenance so later review steps can connect procedure candidates safely.

## Command Usage

Dry-run is the default safe mode:

```powershell
python -m scripts.moleg_live_ingest --law-name "도시개발법" --dry-run
```

Apply requires an explicit flag:

```powershell
python -m scripts.moleg_live_ingest --law-name "도시개발법" --apply
```

The command prints sanitized JSON only. It does not print raw XML, raw HTML, raw request URLs containing `OC`, or API secrets.

## Environment Variables

Required live settings are the same as the MOLEG diagnostics:

- `MOLEG_API_ENABLED=true`
- `MOLEG_LIVE_TEST_ENABLED=true`
- `MOLEG_API_BASE_URL` configured locally
- `MOLEG_API_KEY` or `MOLEG_OC` configured locally
- optional timeout/retry settings

Diagnostics and ingest output may show key presence, key length, fingerprint prefix, selected endpoint, and `trust_env`, but never the raw secret.

## Structure

The ingest pipeline reuses existing components:

- `moleg_probe_service` for endpoint matrix and browser-compatible endpoint selection
- `moleg_live_client` for HTTP transport, XML parsing, redaction, headers, and `trust_env=false` support
- `official_law_source.MolegOpenApiLawSourceProvider` normalization helpers
- existing SQLAlchemy session/database models
- existing law/article as-of version service
- existing official DB fallback chain

No public unauthenticated ingest endpoint is added. The management interface is the CLI script.

## Law Selection Rules

The live search response is not accepted by first-result ordering. The selected candidate must have:

- exact normalized official law name match to the requested law name
- law ID present
- MST/law serial present
- effective date metadata when available

Similar names such as enforcement decree/rule are rejected when the requested law name is the act. The current Phase 37 implementation imports one selected law at a time.

## Transaction And Rollback

`--dry-run` performs search, detail fetch, parse, validation, and insert/update planning, then rolls back and leaves DB row counts unchanged.

`--apply` writes inside a transaction. If an error occurs before commit, the session rolls back and reports `rollback=true`. Tests also cover a forced rollback path.

## Idempotency Policy

Natural identifiers are used without adding new migration constraints:

- Law: `law_key = moleg:<law_id>`
- Law article: deterministic key from live article order, article number, anchor, and title hash
- Law article version: `law_article_id + effective_date + source`, where `source = MOLEG_LIVE:<MST>`
- Official document: existing unique provider/law_id/MST/enforcement_date key
- Official article: document, sort order, article number, and anchor matching

Running the same `--apply` again should create no duplicate law/article/version/document/article rows. Each apply still records an ingest run and sanitized evidence summary as provenance.

## Stored Tables

Phase 37 stores normalized data in:

- `laws`
- `law_articles`
- `law_article_versions`
- `official_law_documents`
- `official_law_articles`
- `official_law_ingest_runs`
- `official_law_source_evidence`

There is no separate law-version table in the current schema. Law version identity is represented by official document MST/effective date and by article versions sourced as `MOLEG_LIVE:<MST>`.

## Raw Payload And Secret Policy

Do not store or print:

- API key or `OC`
- request URL with secret query values
- raw XML
- raw HTML
- raw full response payload

Stored evidence contains sanitized summary metadata only: selected law name, law ID, MST, effective date, endpoint host/path, article count, parser version, fetched timestamp, and policy flags.

`law_article_versions.raw_payload_json` is set to `null` for live MOLEG ingest.

## As-Of Verification

After apply, verify versions through the existing API/service:

```powershell
# list laws, find law id
# then query as-of article summaries
GET /api/laws/{law_id}/articles?as_of=2025-01-01
GET /api/laws/{law_id}/articles?as_of=2026-07-01
```

The existing `law_version_service` classifies article versions as `scheduled`, `current`, `previous`, or `unknown_effective_date` based on effective date.

## Analyze Integration

`/api/analyze` keeps the existing fallback behavior. Phase 37 does not infer procedure-to-article mappings from law names alone. If there is no reviewed or confirmed article candidate, procedure legal references remain candidate/needs-review according to existing policy.

Fallback order remains:

1. `official_seed_db`
2. `official_manual_db`
3. `procedure_keyword_candidate`
4. `needs_review`

## Recovery

If an apply fails before commit, rerun the command after fixing the cause. If a run completed but needs to be superseded, rerun `--apply`; unchanged rows are skipped, and changed normalized article text/version fields are updated idempotently. Do not delete manual seed/manual official data while recovering a live ingest run.

## Live Tests

Default pytest uses mock MOLEG responses and does not call the external API. Actual live verification is done through CLI smoke/ingest commands only when local live env is configured.
