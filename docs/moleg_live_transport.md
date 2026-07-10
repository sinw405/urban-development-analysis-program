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

## Phase35 Probe Workflow

Phase35 separates MOLEG live diagnostics into explicit probes:

- `config_probe`: checks `.env` loading, enable flags, base URL presence, key presence, key length, SHA-256 fingerprint prefix, timeout, retry count, and allowed env names. It never prints the raw key.
- `network_probe`: checks host DNS, socket connection, and TLS handshake for the configured base URL.
- `search_probe`: sends a live law search request such as query `도시개발법` when live diagnostics are enabled and configured.
- `detail_probe`: if search returns a law identifier, attempts a detail request for that identifier.
- `parse_probe`: confirms whether the response can be parsed as JSON or XML.
- `storage_policy_probe`: confirms that raw payload storage is disabled and secrets are not exposed.

Smoke commands:

```powershell
python -m scripts.smoke_moleg_transport --probe config
python -m scripts.smoke_moleg_transport --probe network
python -m scripts.smoke_moleg_transport --probe search --query "도시개발법"
python -m scripts.smoke_moleg_transport --probe all
```

The smoke output includes `final_reason_type`, `reason_message_ko`, `suggested_fix`, probe result summaries, and `secret_exposed=false`. It does not print raw request URLs with live keys, raw JSON/XML payloads, or full response bodies.

## Redacted Config Check

Diagnostics may show:

- `live_enabled`
- `configured`
- `key_present`
- `key_length`
- `key_fingerprint_sha256_prefix`
- `configured_env_names`
- `detected_env_names_without_values`
- sanitized base URL and endpoint path
- timeout and retry settings

Diagnostics must not show the raw `MOLEG_API_KEY`, raw `MOLEG_OC`, request headers, or query strings containing live secrets. Query parameters such as `OC`, `serviceKey`, `key`, and `token` must be redacted.

## Phase35 Reason Types

- `ok`: live response was reachable and parseable.
- `not_configured`: required env/config values are missing.
- `live_disabled`: live probes are disabled by `MOLEG_LIVE_TEST_ENABLED=false`.
- `invalid_base_url`: base URL is missing a valid HTTP/HTTPS scheme or host.
- `dns_error`: DNS resolution failed.
- `connection_timeout`: network or HTTP request timed out.
- `connection_refused`: socket connection was refused.
- `tls_error`: TLS handshake or certificate validation failed.
- `proxy_error`: proxy configuration or proxy connection failed.
- `http_error_status`: HTTP status was an error not mapped to a more specific reason.
- `unauthorized_or_invalid_key`: HTTP/API response indicates invalid key or unauthorized access.
- `invalid_request_parameter`: endpoint or required request parameter is invalid.
- `invalid_response_format`: response is not recognizable as JSON/XML.
- `empty_response`: response body is empty.
- `html_error_response`: endpoint returned HTML, often a proxy/block/error page.
- `api_error_response`: MOLEG returned an API-level error payload.
- `parsing_error`: JSON/XML parsing failed.
- `unknown_connection_error`: fallback when the error cannot be classified safely.

## Official API Contract Note

If official MOLEG API documentation is not available in the project workspace, do not invent endpoint rules or parameter meanings. Use sanitized live response diagnostics to identify whether the current request path, authentication parameter `OC`, `type=JSON/XML`, `target=law`, search query, and detail identifier are accepted. Any change to endpoint or parameter contracts should be backed by official documentation or a sanitized successful live smoke.

## Phase36 Path

When `--probe all` reaches `final_reason_type=ok`, Phase36 can add controlled live ingest/import. That phase should still avoid storing raw JSON/XML payloads and should persist only normalized metadata, article identifiers, titles, anchors, dates, source metadata, and reviewed summaries needed by the application.

If live probes fail, fallback remains active in this order:

1. `official_seed_db`
2. `official_manual_db`
3. `procedure_keyword_candidate`
4. `needs_review`
