# Phase 23 Live Official Law Response Normalization

## Purpose

Phase 23 extends the Phase 22 MOLEG Open API adapter so live law search and law body responses can be normalized into stable internal structures before Phase 24 database ingestion.

The default app path still uses mock mode. Live calls only run when local environment variables explicitly enable them.

## Live Smoke Preparation

Keep real keys outside git-tracked files. A local `.env` may contain:

```text
MOLEG_API_ENABLED=true
MOLEG_OC=<your local secret>
MOLEG_API_KEY=<your local secret>
MOLEG_API_BASE_URL=https://www.law.go.kr
MOLEG_API_TIMEOUT_SECONDS=10
MOLEG_LIVE_TEST_ENABLED=true
```

`MOLEG_API_KEY` and `MOLEG_OC` are aliases in this project. The official request parameter sent by the adapter is `OC`.

## Law Search Endpoint

```text
GET /DRF/lawSearch.do
target=law
type=JSON
query=?????
page=1
display=20
OC=<secret>
```

The adapter tries JSON first and retries XML when JSON normalizes to no candidates.

Search normalization extracts:

```text
title
short_title
law_id
mst
promulgation_date
enforcement_date
is_current
source_url
match_score
match_reason
pagination
```

## Law Body Endpoint

```text
GET /DRF/lawService.do
target=law
type=JSON
MST=<selected search candidate MST>
OC=<secret>
```

The adapter uses the selected candidate's `MST` as the primary body lookup identifier. It normalizes law title, law id, MST, enforcement date, and article units. JSON is tried first; XML is used as fallback if no article units normalize.

## Identifier Handling

`MST` is treated as the primary live body lookup key. `??ID`, `ID`, `LM`, and related fields are preserved as `law_id` when present. Candidate and document schemas retain both `mst` and `law_id` so Phase 24 can decide which identifiers to persist.

## Pagination Handling

Pagination fields are normalized opportunistically from `totalCnt`, `total_count`, `totalCount`, `page`, `pageNo`, `display`, `numOfRows`, and similar response fields. If total count and page size are available, `total_pages` is calculated.

## Normalized Schemas

Phase 23 adds these internal schemas:

```text
OfficialLawSearchResult
OfficialLawCandidate
OfficialLawPagination
OfficialLawDocument
OfficialLawArticle
```

Existing Phase 20-22 snapshot schemas remain available for verify-preview response compatibility.

## Candidate Ranking

Candidate ranking prioritizes:

```text
1. Exact title match
2. Exact short-title match
3. Title starts with query
4. Title contains query
5. Current-law signal
6. MST presence
```

The selected candidate is the highest score candidate. The `match_reason` explains why it won.

## Candidate Verification Statuses

`matched`: law name, article number, title or keyword, and source URL are sufficient.

`partial`: a source snapshot exists but article/title/content confidence is incomplete.

`unmatched`: no law/article source is found.

`source_unavailable`: live mode was requested but credentials/configuration are missing.

`source_error`: timeout, HTTP failure, parsing failure, or live source failure occurred.

## Mock, Fixture, And Live Modes

`mock` mode uses in-process Phase 20 fixtures and makes no network calls.

`fixture` tests use sanitized minimal payloads that resemble MOLEG search/body responses. They do not include real OC values or full live payloads.

`live` mode calls the configured MOLEG endpoint only when `MOLEG_LIVE_TEST_ENABLED=true` and credentials are present. If the source cannot be reached, tests record source_error behavior without exposing secrets.

## Secret Redaction Policy

The adapter never returns `OC` or API keys in API responses. Source URLs are sanitized to endpoint paths without query strings. Debug payload samples are limited and attached only to `raw_payload_redacted` fields excluded from Pydantic serialization.

Secret key names and secret values are replaced with `[REDACTED]`.

## Current Limits

Phase 23 does not persist official payloads. It does not promote candidate references to verified. Live response variation may still require additional field aliases after more real-world samples are reviewed.

## Phase 24 Tasks

Phase 24 should design DB persistence for normalized official law documents, decide MST/law_id storage rules, preserve audit evidence, and add an operator workflow for candidate-to-verified promotion.
