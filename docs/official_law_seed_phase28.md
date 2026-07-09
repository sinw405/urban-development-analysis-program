# Phase28: Official Law Seed Import Workflow

## Purpose

Phase28 prepares a controlled official seed workflow for urban development law, enforcement decree, and enforcement rule documents. It does not create or invent legal text, article numbers, thresholds, or criteria.

The goal is to import official JSON/XML files provided by the user or obtained from an official source into `official_law_documents` and `official_law_articles` through the same normalized persistence path used by manual import.

## Why Seed Import Is Needed While Live API Fails

MOLEG live transport can still fail in the local environment. The DB-first preview flow can continue if official snapshots are populated from reviewed JSON/XML files. Seed import provides that path without relying on live network access.

## Directory Structure

```text
backend/seeds/official_laws/
  README.md
  manifest.example.json
  urban_development/
    .gitkeep
    README.md
```

Place files under `backend/seeds/official_laws/urban_development/` when available. Suggested names:

- `urban_development_law.json` or `.xml`
- `urban_development_enforcement_decree.json` or `.xml`
- `urban_development_enforcement_rule.json` or `.xml`

Do not commit unreviewed raw dumps or files containing request URLs with secrets.

## Manifest Format

Use `manifest.example.json` as a schema guide. Required fields include:

- `source_provider`
- `mode`
- `law_title`
- `source_file`
- `source_format`
- `expected_min_article_count`

Optional metadata includes `law_short_title`, `law_id`, `mst`, `enforcement_date`, `promulgation_date`, `document_status`, `is_current`, and `notes`.

Placeholder values such as `<LAW_ID>` or `<OFFICIAL_SOURCE_FILE>` are intentionally rejected by preflight validation.

## Preflight Validation

Seed import checks:

- manifest file exists
- manifest parses as JSON
- placeholder values are not present
- `source_file` exists
- `source_format` is `json` or `xml`
- `source_file` extension matches `source_format`
- `law_title` and `source_provider` are present
- `expected_min_article_count` is at least 1
- missing `law_id`, `mst`, or `enforcement_date` generates warnings but does not block storage
- actual article count below `expected_min_article_count` generates a warning

## Import API

```http
POST /api/legal-references/official-law-seed-import
Content-Type: application/json

{
  "manifest_path": "backend/seeds/official_laws/urban_development/manifest.json"
}
```

Response includes status, `source_mode=official_seed`, `source_mode_detail=official_seed_db`, document/article counts, ingest run id, source metadata, warnings, and `secret_exposed=false`.

## Manual Import vs Seed Import

Manual import is for ad hoc file loading and uses `source_mode=official_manual`.

Seed import is for curated official seed files and uses `source_mode=official_seed`. When loaded through DB-first verification, the compatibility `source_mode` remains `official_db`, while `source_mode_detail` identifies `official_seed_db` or `official_manual_db`.

## Raw Payload Policy

Raw JSON/XML payloads are not stored in evidence. Evidence stores only sanitized summaries such as file name, source mode, source provider, selected title/MST, document title/MST, article count, and sanitized source hint.

## Verify-preview Relationship

`verify-preview` remains DB-first:

1. official DB snapshot, including seed/manual imported documents
2. live fallback only when requested and no DB snapshot exists
3. mock fallback when live is unavailable or fails

Seed import lets Phase29 map procedure steps to official article candidates from stored snapshots without depending on live API availability.
