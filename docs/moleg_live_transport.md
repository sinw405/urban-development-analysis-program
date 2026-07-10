# MOLEG Live Transport Diagnostics

## Purpose

This phase stabilizes the live transport layer for the 법제처 Open API. Live MOLEG responses are used only for connectivity diagnostics and future reviewed ingestion paths. The application analysis flow must remain safe when MOLEG live transport is unavailable.

## Environment Variables

Use local `.env` only for secrets. Do not place real keys in code, tests, docs, logs, or API examples.

Required or supported names:

- `MOLEG_API_ENABLED=true|false`
- `MOLEG_LIVE_TEST_ENABLED=true|false`
- `MOLEG_API_BASE_URL=https://www.law.go.kr`
- `MOLEG_API_KEY=<local secret>`
- `MOLEG_OC=<local secret alias>`
- `MOLEG_API_TIMEOUT_SECONDS=5`
- `MOLEG_API_RETRY_COUNT=1`
- `MOLEG_API_RETRY_BACKOFF_SECONDS=0.25`

`MOLEG_API_KEY` and `MOLEG_OC` are aliases. Diagnostics may show whether a key is present, key length, and a short SHA-256 fingerprint prefix. They must not show the raw secret or raw query string.

## Secret And Raw Payload Policy

- Never expose API keys, OC values, service keys, full request URLs with secret query parameters, or raw exception repr strings.
- Never store full MOLEG JSON/XML payloads in seed/manual evidence.
- Never store full law article body text in seed/manual evidence.
- Evidence should contain sanitized summaries, article title/anchor/reference metadata, source mode metadata, file names, and counts only.
- Actual article numbers, thresholds, and review requirements must be finalized only through the live API response or reviewed official seeds, not by guessing.

## Diagnostic Endpoint

Use:

```text
GET /api/legal-references/moleg/diagnostic
```

The response includes:

- `live_enabled`
- `configured`
- `transport_ok`
- `reason_type`
- Korean `reason_message`
- sanitized `diagnostic_detail`
- `next_action`
- `secret_exposed=false`
- `raw_payload_stored=false`
- `request_sanitized=true`
- `fallback_available=true`
- `fallback_source_modes`

Legacy endpoints remain available for compatibility:

- `GET /api/legal-references/official-laws/diagnostic`
- `GET /api/legal-references/moleg-live-diagnostic`
- `GET /api/legal-references/moleg-transport-diagnostic`

## Smoke Script

Run:

```bash
python -m scripts.smoke_moleg_transport
```

Behavior:

- live disabled: prints `status=skipped`, exits 0
- not configured: prints `status=skipped`, exits 0
- external transport failure: prints `status=source_error` and `reason_type`, exits 0
- code/parsing logic crash outside the diagnostic policy: prints `status=error`, exits 1

The script does not print raw secrets, raw full URLs, raw XML, or raw JSON payloads.

## Reason Types

- `ok`: API returned a parseable JSON/XML response.
- `not_configured`: required enable flag, base URL, or key is missing.
- `live_disabled`: live diagnostics are intentionally disabled.
- `invalid_base_url`: base URL is missing scheme or host.
- `dns_error`: host DNS lookup failed.
- `connection_timeout`: socket or HTTP request timed out.
- `connection_refused`: remote connection was refused.
- `tls_error`: TLS/certificate/security connection failed.
- `http_error_status`: endpoint returned HTTP 4xx/5xx.
- `invalid_response_format`: response was empty, HTML, or not JSON/XML.
- `api_error_response`: MOLEG returned an API-level error payload.
- `parsing_error`: response looked like JSON/XML but parser failed.
- `unknown_connection_error`: sanitized fallback for unclassified connection failures.

## Fallback Policy

MOLEG live failure must not fail `/api/analyze`. Official article candidate resolution keeps this order:

1. `official_seed_db`
2. `official_manual_db`
3. `procedure_keyword_candidate`
4. no candidate / `검토 필요`

If no reviewed candidate exists, the system must leave the procedure as review-needed. It must not invent article numbers, legal thresholds, or review requirements.
