# Phase27: MOLEG Transport Probe And Manual Official Law Import

## Purpose

Phase27 adds two safeguards around official law sourcing.

1. It narrows the Phase26 `unknown_connection_error` by probing DNS, socket, TLS, proxy, HTTP, and endpoint reachability separately.
2. It adds a manual JSON/XML import path so development can continue when the live MOLEG Open API is unavailable.

The existing DB-first verification flow remains unchanged: stored official law snapshots are checked before live fallback and mock fallback.

## Remaining Phase26 Symptom

Phase26 confirmed that live configuration and a local secret can be detected safely, but the live-only diagnostic still returned `unknown_connection_error`. This means the request did not reach a parseable MOLEG response and the failure needed transport-level separation.

## Transport Diagnostic Endpoint

```http
GET /api/legal-references/moleg-transport-diagnostic
```

The endpoint returns sanitized transport probe fields:

- configured host, scheme, and port
- proxy environment detection
- DNS resolution status
- socket connect status
- TLS/SSL handshake status
- HTTP endpoint status
- status code when available
- reason type and sanitized error class/message
- elapsed time
- suggested next action

Possible `reason_type` values include:

- `dns_error`
- `socket_timeout`
- `socket_connection_error`
- `tls_error`
- `ssl_error`
- `proxy_error`
- `connection_refused`
- `http_error`
- `invalid_response`
- `parse_error`
- `unknown_connection_error`
- `ok`

## PowerShell Manual Checks

Use placeholders only. Never paste a real key into committed files.

```powershell
$env:MOLEG_OC = "<MOLEG_API_KEY>"
Resolve-DnsName www.law.go.kr
Test-NetConnection www.law.go.kr -Port 443
Invoke-WebRequest -Method GET "https://www.law.go.kr/DRF/lawSearch.do?target=law&type=JSON&query=%EB%8F%84%EC%8B%9C%EA%B0%9C%EB%B0%9C%EB%B2%95&OC=$env:MOLEG_OC"
```

## curl Manual Check

```bash
MOLEG_OC="<MOLEG_API_KEY>"
curl -v -G "https://www.law.go.kr/DRF/lawSearch.do" \
  --data-urlencode "target=law" \
  --data-urlencode "type=JSON" \
  --data-urlencode "query=도시개발법" \
  --data-urlencode "OC=${MOLEG_OC}"
```

## Secret Masking Policy

- API keys, OC, serviceKey, full secret-bearing URLs, and request headers must not be returned or logged.
- Diagnostic URLs use `<redacted>` style placeholders only.
- Response bodies are limited to short sanitized previews.
- Raw live payloads are not stored in the database.
- Evidence rows store sanitized summaries only.

## Manual Import Endpoint

```http
POST /api/legal-references/official-law-manual-import
Content-Type: application/json

{
  "file_path": "C:/path/to/manual_moleg_response.json",
  "query": "<law title from the file>",
  "source_provider": "moleg_manual_upload",
  "source_mode": "official_manual"
}
```

Supported files:

- JSON
- XML

The file must contain a structure that the existing MOLEG normalizer can parse into an `OfficialLawDocument` and article units. If parsing is uncertain, the endpoint returns `source_error` with `invalid_response` or `parse_error` and does not invent law titles, article numbers, or body text.

## Manual Import Storage Policy

Successful manual import writes:

- `official_law_documents`
- `official_law_articles`
- `official_law_ingest_runs`
- `official_law_source_evidence`

The document uses `source_mode=official_manual`. Duplicate imports reuse the existing document according to the existing source provider, law ID, MST, and enforcement date policy. Evidence stores only a sanitized summary such as file name, selected title/MST, document title/MST, article count, and sanitized source hint.

## DB-first Relationship

Manual import is a way to populate the same DB snapshot store used by `verify-preview`. Once imported, the preview flow remains:

1. `official_db` snapshot
2. live fallback when requested and no DB snapshot exists
3. mock/fallback if live is unavailable or fails

Therefore live transport failure must not break preview responses when a matching official DB snapshot exists.

## Live API Priority After Connectivity Is Fixed

Manual import is an operational fallback. If live MOLEG connectivity is fixed and response normalization is confirmed, controlled live ingest can be preferred over manual upload for fresh official data.

## Phase28 Direction

Phase28 can move toward controlled official seed loading for urban development law, enforcement decree, and enforcement rule snapshots. The import path and DB-first lookup added here provide the foundation for that work without hard-coding legal criteria or article numbers.
