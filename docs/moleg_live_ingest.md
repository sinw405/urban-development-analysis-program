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

## Phase 38 law family ingest

Phase 38 extends the same live ingest service to a configured law family. The current registry is held in one place in `moleg_live_ingest_service.py` as `LAW_FAMILY_REGISTRY`:

- `urban-development`
- 도시개발법
- 도시개발법 시행령
- 도시개발법 시행규칙

Single-law execution remains supported:

```powershell
python -m scripts.moleg_live_ingest --law-name "도시개발법" --dry-run
python -m scripts.moleg_live_ingest --law-name "도시개발법" --include-history 2 --apply
```

Law-family execution uses the same dry-run default and requires `--apply` for persistence:

```powershell
python -m scripts.moleg_live_ingest --law-family urban-development --dry-run
python -m scripts.moleg_live_ingest --law-family urban-development --include-history 2 --apply
```

`--include-history N` means: ingest up to `N` immediately previous exact-name candidates if the MOLEG search response exposes them. The code does not hardcode MST values or invent historical versions. If the live source only returns the current exact candidate, the result reports `history_status=not_available_from_source`.

## Version status

Each selected exact candidate is classified as:

- `current`: latest exact candidate whose effective date is on or before the execution date
- `historical`: older exact candidate selected by `--include-history`
- `scheduled`: exact candidate whose effective date is after the execution date

The current schema has no separate law-version table. Version identity is represented by:

- `official_law_documents.source_provider/law_id/mst/enforcement_date`
- `law_article_versions.source = MOLEG_LIVE:<MST>`
- `law_article_versions.effective_date`

## Transaction policy

Law-family ingest uses a per-law transaction policy. A failure in one law rolls back that law's transaction and reports the failed law and reason. Other laws are allowed to complete. The batch result reports `completed`, `partial_success`, or `failed`.

## As-of coverage

`GET /api/laws/{law_id}/articles?as_of=YYYY-MM-DD` remains backward-compatible and still returns `items`. Phase 38 adds metadata:

- `requested_as_of`
- `coverage_status`
- `available_from`
- `available_to`
- `total_articles`
- `applicable_articles`
- `current_version_count`
- `selected_mst`
- `selected_effective_date`
- `version_status`
- `history_complete`

`coverage_status=before_available_history` means the database has no stored version applicable to the requested date. The API must not present the latest known version as if it applied to that earlier date. In that case `current_version_count` and `applicable_articles` are `0`.

## Version diff

Stored versions can be compared without using an LLM:

```powershell
python -m scripts.moleg_version_diff --law-name "도시개발법" --from-mst <MST> --to-mst <MST>
```

The diff uses normalized article title/body text and classifies articles as:

- `added`
- `removed`
- `changed`
- `unchanged`

The output includes law name, law ID, from/to MST, effective dates, counts, changed article identifiers, generated timestamp, source provenance, and policy flags. It never prints raw XML/HTML or secret query values.

If a requested MST is not stored, the result is `status=missing_version` and `reason_type=version_not_available`. Do not create fake historical data to satisfy a diff request.

## Phase 38 live source limitation

In the current live smoke, MOLEG `lawSearch.do` exposed the current exact version for each urban-development law. Previous or scheduled exact versions were not returned by that search response, so the ingest result reports `history_status=not_available_from_source`. Historical ingest should proceed only when MOLEG exposes official metadata for those versions or a reviewed official source is provided.
