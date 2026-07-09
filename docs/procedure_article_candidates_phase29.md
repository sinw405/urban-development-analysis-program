# Phase29 Procedure Article Candidates

## Purpose

Phase29 connects stored official law snapshots to urban development procedure steps as unconfirmed official article candidates. The goal is to prepare `/api/analyze` and legal reference preview flows to surface possible article evidence without treating those articles as verified legal references.

This phase does not create or infer legal article numbers, thresholds, area criteria, or final legal conclusions.

## Official Snapshot To Procedure Step

`official_law_documents` and `official_law_articles` are the source tables for candidate search. Phase29 adds `procedure_official_article_candidates` as a separate candidate table so generated candidates can be reviewed, counted, and later promoted only after expert validation.

The resolver searches stored articles by:

- procedure code and procedure name
- preferred law title or short title
- article title keyword match
- article source anchor or source hint match
- article text keyword match

Keyword matches are only discovery hints. They are not legal determinations.

## Candidate Vs Confirmed Reference

A candidate is a possible article match that needs review. A confirmed reference is a reviewed legal reference that can be relied on by the product.

Phase29 candidates are stored with:

- `match_status=candidate` or `weak_candidate`
- `is_confirmed=false`
- `confidence_level=high|medium|low|unknown`

`is_confirmed=true` is reserved for a later expert review workflow. Fixture results must never be promoted automatically.

## Why Article Numbers Are Not Invented

Article numbers and legal basis values must come from official source files or reviewed DB snapshots. The keyword config intentionally does not contain article numbers, thresholds, or legal criteria. If official seed files are missing, the system returns empty candidates or unmatched steps instead of fabricating references.

## Keyword Config

The Phase29 keyword config is stored at:

```text
rules/procedure_article_keywords.yaml
```

Each entry may contain:

- `procedure_code`
- `procedure_name`
- `preferred_laws`
- `keywords`
- `required`

The config is used only to locate candidate articles. It should not be treated as a legal rule source.

## Source Mode Detail

Candidate source distinction is preserved:

- `source_mode=official_db`, `source_mode_detail=official_seed_db` for official seed imports
- `source_mode=official_db`, `source_mode_detail=official_manual_db` for manual imports
- `source_mode=fixture`, `source_mode_detail=fixture_only` for test-only fixtures

The public verify-preview compatibility field can remain `source_mode=official_db`, while `source_mode_detail` carries the exact origin.

## API Shape

Phase29 adds:

```text
GET /api/legal-references/procedure-article-candidates
```

Optional query parameters:

- `procedure_code`
- `law_title`
- `source_mode_detail`
- `include_unmatched`

Response groups candidates by procedure step and includes `unmatched_steps` plus warnings when no candidate exists.

## Analyze Integration

`/api/analyze` keeps the existing procedures list and adds optional candidate fields to each step:

- `official_article_candidates`
- `legal_reference_candidates`
- `reference_candidate_count`
- `reference_status`

No official candidate means analysis still succeeds. The status becomes `no_official_candidate` or `needs_seed_data` depending on the available inputs.

## Unmatched Steps

Unmatched steps are reported explicitly. This means the current official snapshot does not contain a keyword candidate for that procedure step. It does not mean there is no legal requirement.

## Security And Evidence

Phase29 does not store raw live payloads. Seed/manual evidence remains sanitized summary only. API keys, OC values, service keys, and raw request URLs must not appear in logs, API responses, committed files, or evidence rows.

## Phase30

Phase30 can connect 심의 and 평가 판별 rules to official article candidates. That work should still keep candidates separate from confirmed references until expert review promotes them.
