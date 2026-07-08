# Phase 21 Official Law API Integration Preparation

## Purpose

Phase 21 prepares a secure adapter boundary for future MOLEG Open API or National Law Information Center integration. It does not require a real API key for normal development or CI, and it keeps the Phase 20 mock provider and verify-preview flow intact.

## Environment Variables

```text
MOLEG_API_ENABLED=false
MOLEG_API_BASE_URL=
MOLEG_API_KEY=
MOLEG_OC=
MOLEG_API_TIMEOUT_SECONDS=5
MOLEG_LIVE_TEST_ENABLED=false
```

`MOLEG_API_KEY` is the preferred secret variable. `MOLEG_OC` is accepted as an alias for environments that use the official parameter name.

`MOLEG_API_BASE_URL` should contain the reviewed official endpoint base URL when live integration is tested.

`MOLEG_API_TIMEOUT_SECONDS` controls live request timeout handling.

`MOLEG_LIVE_TEST_ENABLED` must be enabled explicitly before live smoke tests run.

## API Key Storage

Do not commit real API keys. Keep local secrets in `.env`, `.env.local`, deployment secret stores, or CI secret variables. The repository only contains `.env.example` with empty placeholders.

The adapter never includes the API key in preview API responses. Provider errors are converted to generic `source_unavailable` or `source_error` statuses.

## Mock, Fixture, And Live Modes

`mock` mode is the default. It uses `MockOfficialLawSourceProvider`, makes no network calls, and keeps tests deterministic.

`fixture` behavior is represented by in-process mock article snapshots. It is useful for matched, partial, and unmatched verification preview tests.

`live` mode uses `MolegOpenApiLawSourceProvider`. It is only usable when `MOLEG_API_ENABLED=true`, a base URL is present, and either `MOLEG_API_KEY` or `MOLEG_OC` is present. If live mode is requested without configuration, preview returns `source_unavailable` instead of failing the request.

## Live Smoke Execution

Normal test runs do not require live API credentials.

To opt in locally, set environment variables outside git-tracked files:

```text
MOLEG_API_ENABLED=true
MOLEG_API_BASE_URL=<reviewed official endpoint base URL>
MOLEG_API_KEY=<local secret>
MOLEG_LIVE_TEST_ENABLED=true
```

Then run:

```text
python -m pytest tests/test_official_law_source_phase21.py
```

The live smoke attempts candidate law/article lookup and normalizes any usable response into the internal official law source snapshot schema.

## Current Limits

The live adapter is a safe preparation layer, not a completed production MOLEG integration. Endpoint paths, official response variants, pagination, law IDs, article IDs, and exact parameter contracts still need review against official documentation and real sample responses.

The adapter does not store official payloads in the database and does not promote any candidate reference to verified.

## Phase 22 Tasks

Phase 22 should validate official endpoint contracts, add reviewed request parameter builders, preserve raw official payload snapshots, define law/article identifier mapping rules, add controlled persistence if needed, and design a reviewed promotion workflow from candidate to verified.
