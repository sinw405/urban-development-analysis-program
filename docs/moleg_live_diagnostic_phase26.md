# Phase26: MOLEG Live Diagnostic Hardening

## Purpose

Phase26 separates live-only MOLEG connectivity diagnostics from the DB-first legal reference flow. The diagnostic endpoint checks the actual live request path without using `official_law_documents` fallback, while `verify-preview` continues to use DB snapshot first and live/mock fallback only when needed.

## Current Connection Error

The local environment can detect MOLEG live configuration and the presence of a secret, but live calls may still return a sanitized `source_error` such as `dns_error`, `timeout`, `ssl_error`, `proxy_error`, `connection_refused`, `http_error`, `invalid_response`, `parse_error`, or `unknown_connection_error`.

A live connection error is not a DB-first verification blocker. Stored official-law snapshots remain the preferred evidence source for preview responses.

## Diagnostic Endpoint

Use this endpoint for live-only diagnostics:

```http
GET /api/legal-references/moleg-live-diagnostic
```

The response includes only sanitized data:

- `live_configured`
- `has_secret`
- `secret_exposed`
- `sanitized_base_url`
- `sanitized_endpoint`
- `final_url_sanitized`
- `request_method`
- `query_keys`
- `timeout_seconds`
- `status_code`
- `reason_type`
- `error_class`
- `error_message_sanitized`
- `elapsed_ms`
- `response_content_type`
- `response_preview_sanitized`
- `suggested_next_action`

The endpoint does not return the raw OC/API key, request headers, or full raw response body.

## Endpoint And Parameters

The live diagnostic uses:

- base URL: `MOLEG_API_BASE_URL`, usually `https://www.law.go.kr`
- endpoint: `/DRF/lawSearch.do`
- method: `GET`
- target: `law`
- type: `JSON`
- query: `도시개발법`
- auth parameter: `OC`

The client validates required parameters before sending the request. Missing base URL, disabled flags, or missing secret produce a safe diagnostic response instead of an unhandled exception.

## PowerShell Reproduction

Set a local-only variable, then run a direct request. Do not commit the value.

```powershell
$env:MOLEG_OC = "<MOLEG_API_KEY>"
Invoke-WebRequest -Method GET "https://www.law.go.kr/DRF/lawSearch.do?target=law&type=JSON&query=%EB%8F%84%EC%8B%9C%EA%B0%9C%EB%B0%9C%EB%B2%95&OC=$env:MOLEG_OC"
```

If sharing output, remove or mask the `OC` value and avoid sharing the full raw response unless it has been reviewed for secrets.

## curl Reproduction

```bash
MOLEG_OC="<MOLEG_API_KEY>"
curl -G "https://www.law.go.kr/DRF/lawSearch.do" \
  --data-urlencode "target=law" \
  --data-urlencode "type=JSON" \
  --data-urlencode "query=도시개발법" \
  --data-urlencode "OC=${MOLEG_OC}"
```

Do not paste a real key into documentation, commits, screenshots, or issue comments.

## .env Check

Local `.env` may contain:

```dotenv
MOLEG_API_ENABLED=true
MOLEG_OC=<MOLEG_API_KEY>
MOLEG_API_KEY=<MOLEG_API_KEY>
MOLEG_API_BASE_URL=https://www.law.go.kr
MOLEG_API_TIMEOUT_SECONDS=10
MOLEG_LIVE_TEST_ENABLED=true
```

`.env`, `.env.local`, and `*.env.local` must remain ignored. The repository should only contain safe placeholders in `.env.example` or documentation.

## Secret Masking Policy

- Full URLs are sanitized before returning from API responses.
- `OC`, `MOLEG_OC`, `MOLEG_API_KEY`, `serviceKey`, and similar secret keys are redacted.
- Response previews are truncated and sanitized.
- Raw live payloads are not stored in `official_law_source_evidence`.
- Evidence remains a sanitized summary only.

## Network Checks

If `reason_type` is not `ok`, check:

- DNS resolution for `www.law.go.kr`
- outbound firewall policy
- corporate proxy settings: `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`
- SSL inspection or local certificate trust
- timeout value in `MOLEG_API_TIMEOUT_SECONDS`
- whether the `OC` key is valid for the requested Open API
- whether the endpoint is reachable from the runtime host, not only from a browser

## Live Success And Ingest

When live diagnostic returns `ok`, the next step is to run the existing ingest preview for a controlled query and persist normalized results to `official_law_documents` / `official_law_articles`. If parsing is uncertain, the ingest should return `invalid_response` or `parse_error` and avoid storing raw payloads.

## Why DB-first Verify-preview Still Works

`verify-preview` should continue resolving evidence in this order:

1. `official_db` snapshot
2. live fallback only when requested and no DB snapshot is available
3. mock/fallback response when live is unavailable or fails

This keeps legal-reference preview stable even when external connectivity is degraded.
