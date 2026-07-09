# Procedure Article Seed Curation

## Purpose

Procedure article seeds keep reviewed official article candidates separate from generated keyword candidates. They help an operator move from candidate discovery to confirmed article references without relying on MOLEG live connectivity or an LLM/RAG layer.

Phase30 does not create legal article numbers, thresholds, deliberation triggers, or final legal criteria. Those values must come from official law files and human review.

## Candidate And Confirmed Candidate

A candidate is an unreviewed possible match between a procedure step and an official law article. It has `is_confirmed=false` and should be shown as `검토 필요`.

A confirmed candidate is a reviewed candidate. It has `is_confirmed=true`, `confirmed_at`, and confirmation metadata such as `confirmed_by`, `confirmed_source`, or `confirmation_note`. Confirmed candidates are still stored separately from legacy legal reference mappings so the review trail is explicit.

## Source Mode

Use the compatibility field and detail field together:

- `source_mode=official_db`, `source_mode_detail=official_seed_db`: imported from official seed files
- `source_mode=official_db`, `source_mode_detail=official_manual_db`: imported through manual official file upload/import
- `source_mode=fixture`, `source_mode_detail=fixture_only`: test-only fixture data

Fixture data must not be presented as official legal content.

## Raw Payload Policy

Do not store raw MOLEG JSON/XML payloads, full request URLs with secrets, service keys, OC values, or full article body text in seed/manual evidence. Evidence should keep only sanitized summaries, article identifiers, titles, anchors, source mode metadata, file names, and counts.

This keeps secret values out of the database and prevents the audit evidence table from becoming an unbounded raw law archive.

## Adding New Candidates

1. Import official law JSON/XML through the seed or manual import workflow.
2. Generate procedure article candidates with `GET /api/legal-references/procedure-article-candidates`.
3. Review the candidate against the official source file.
4. Confirm the candidate only after review.
5. Leave uncertain candidates unconfirmed and document the reason in `confirmation_note` if needed.

Do not add article numbers or legal thresholds by guesswork.

## Candidate Query API

```http
GET /api/legal-references/procedure-article-candidates?procedure_code=PROJECT_BASIC_REVIEW&source_mode_detail=official_seed_db
```

Useful filters:

- `procedure_code`
- `is_confirmed=true|false`
- `source_mode_detail=official_seed_db|official_manual_db|official_db|fixture_only`

The response includes candidate ids, article title/reference fields, match score, confidence, source mode detail, generated timestamp, and confirmation metadata. It does not include raw payloads.

## Confirm API

```http
PATCH /api/legal-references/procedure-article-candidates/{candidate_id}/confirm
Content-Type: application/json

{
  "confirmed_by": "manual_admin",
  "confirmed_source": "manual_admin",
  "confirmation_note": "Reviewed against official seed file."
}
```

The operation is idempotent. Re-confirming an already confirmed candidate keeps it confirmed and updates review metadata.

## Unconfirm API

```http
PATCH /api/legal-references/procedure-article-candidates/{candidate_id}/unconfirm
Content-Type: application/json

{
  "confirmation_note": "Needs re-review after source update."
}
```

This clears `confirmed_at`, `confirmed_by`, and `confirmed_source`, and sets `is_confirmed=false`.

## Seed Validation Script

Run:

```powershell
python -m scripts.validate_procedure_article_seeds --path rules/procedure_article_seed_candidates.json
```

The validator checks that each seed item has a procedure code, law name/title, at least one article reference field, an allowed `source_mode_detail`, no raw payload fields, and confirmation evidence when `is_confirmed=true`.

Forbidden fields include `raw_payload`, `raw_json`, `raw_xml`, and `full_text`.

## MOLEG Live Fallback Policy

MOLEG live transport can still fail with `unknown_connection_error`. That is not a blocker for curation because the DB-first flow uses official seed/manual imports first. Live can be used later as a fallback or ingestion source when connectivity is stable.

## Analyze Output

`/api/analyze` keeps the 13 procedure steps. Candidate fields are optional and display confirmed candidates first. If no confirmed candidate exists, unconfirmed candidates remain visible as review targets.

## Current Limits

Actual Urban Development Act, Enforcement Decree, and Enforcement Rule official seed files are still required for production-grade curation. Until those files are provided and reviewed, candidates remain test or preview data.
