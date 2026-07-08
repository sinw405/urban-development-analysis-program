# Phase 22 Official Law API Live Integration Verification

## Purpose

Phase 22 fixes the MOLEG / National Law Information Center Open API endpoint and parameter structure used by the official law source adapter, adds JSON-first and XML-fallback parsing, and verifies that live smoke can run only when local credentials are explicitly configured.

The default application path still uses mock mode, so API keys are not required for normal tests or local development.

## Official Endpoint Structure

The adapter encapsulates official raw endpoint details inside `MolegOpenApiLawSourceProvider`.

Law search:

```text
GET https://www.law.go.kr/DRF/lawSearch.do
OC=<secret>
target=law
type=JSON
query=?????
```

Law body/article lookup:

```text
GET https://www.law.go.kr/DRF/lawService.do
OC=<secret>
target=law
type=JSON
MST=<law serial id from search result>
```

The adapter tries JSON first. If a response normalizes to no usable records, it retries the same endpoint with `type=XML`. Other services do not depend on raw MOLEG parameter names.

The public Open API guide lists law list lookup and law body lookup as separate API guide categories for current law text. Source: https://open.law.go.kr/LSO/openApi/guideList.do

## Environment Variables

```text
MOLEG_API_ENABLED=true
MOLEG_API_BASE_URL=https://www.law.go.kr
MOLEG_API_KEY=
MOLEG_OC=
MOLEG_API_TIMEOUT_SECONDS=10
MOLEG_LIVE_TEST_ENABLED=true
```

Use either `MOLEG_API_KEY` or `MOLEG_OC`. `MOLEG_API_KEY` is preferred in this project, and `MOLEG_OC` is supported because the official request parameter is `OC`.

## Local .env Example

Do not commit this file. Keep it in local `.env`, `.env.local`, deployment secrets, or CI secrets.

```text
MOLEG_API_ENABLED=true
MOLEG_OC=<your local secret>
MOLEG_API_KEY=<your local secret>
MOLEG_API_BASE_URL=https://www.law.go.kr
MOLEG_API_TIMEOUT_SECONDS=10
MOLEG_LIVE_TEST_ENABLED=true
```

## Live Smoke Execution

Normal verification:

```text
python -m pytest
```

Live-only focused smoke:

```text
python -m pytest tests/test_official_law_source_phase22.py
```

When the live variables are missing or `MOLEG_LIVE_TEST_ENABLED=false`, live tests are skipped and default mock/fixture tests still run.

## Mock, Fixture, And Live Modes

`mock` mode uses `MockOfficialLawSourceProvider` and makes no network calls.

`fixture` coverage is implemented through test payloads that resemble law search and law service responses. These test normalization of law name, MST, article number, title, text, source URL, and effective date.

`live` mode uses `MolegOpenApiLawSourceProvider`. It searches `query=?????`, selects a law candidate, reads the MST identifier, calls law service, and normalizes article snapshots.

## Secret Redaction Policy

The adapter never returns the `OC` or API key in API responses. Request URLs with query strings are not stored as source URLs; only sanitized endpoint URLs are retained.

Debug payloads are stored only in `raw_payload_redacted` fields that are excluded from Pydantic serialization. Secret keys and secret values are replaced with `[REDACTED]` before attachment.

## Candidate Verification Statuses

`matched`: law name, article number, keyword/title signal, and source URL are sufficient.

`partial`: law/article lookup returns an official source snapshot but title or content confidence is incomplete.

`unmatched`: candidate law/article cannot be matched in the selected source.

`source_unavailable`: live mode was requested but API configuration is missing.

`source_error`: timeout, HTTP error, parse error, or other source failure occurred.

## Current Limits

The live adapter supports the current law search/body path and MST-based lookup, but production rollout still needs reviewed response samples across law types, pagination behavior, rate-limit policy, and persistence rules.

Phase 22 does not store official law payloads in the database and does not promote candidate references to verified.

## Phase 23 Tasks

Phase 23 should add reviewed persistence for official law snapshots if needed, define law/article ID mapping rules, add audit evidence for verified promotion, and design an operator workflow for candidate-to-verified approval.
