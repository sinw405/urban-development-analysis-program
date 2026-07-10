# Official Law Seed Bootstrap

## Why Manual Official Seeds Exist

MOLEG live transport can be unavailable or unstable in the local runtime. Manual official seeds provide a safe DB-first source of reviewed official article references without depending on live network access.

This phase does not create real legal article mappings. It creates the file format, validator, importer, diagnostics, and tests needed for future operator-reviewed official seeds.

## Do Not Guess Legal Content

Do not fill article numbers, thresholds, review-trigger requirements, or article summaries from memory or internet search. Enter them only after checking an official source and recording sanitized metadata.

## Seed Location

```text
data/official_law_seeds/
  urban_development_act.seed.yaml
  urban_development_act_enforcement_decree.seed.yaml
  urban_development_act_enforcement_rule.seed.yaml
  examples/official_law_seed.example.yaml
```

The three urban-development files are empty valid templates. The example file uses dummy law/article values only.

## Seed Fields

Top-level fields:

- `seed_version`
- `law_key`
- `law_name`
- `law_type`: `act`, `enforcement_decree`, `enforcement_rule`, or `other`
- `source.source_type`: `official_manual`
- `source.source_name`
- `source.source_url_optional`
- `source.retrieved_at_optional`
- `source.verified_by_optional`
- `source.verification_note_optional`
- `articles`

Article fields:

- `article_key`
- `article_no`
- `article_title`
- `article_anchor`
- `sanitized_summary`
- `effective_date_optional`
- `promulgation_date_optional`
- `status`: `current`, `scheduled`, `historical`, or `unknown`
- `procedure_codes`
- `tags`
- `source_mode_detail`: usually `official_seed_db`
- `confidence`: 0 to 1
- `is_confirmed`
- `confirmation_note`

## Forbidden Fields

The validator rejects these fields anywhere in a seed file:

- `raw_payload`
- `raw_json`
- `raw_xml`
- `full_text`
- `article_full_text`
- `original_body`
- `body`
- `content_raw`

It also rejects `source_url_optional` query parameters such as `serviceKey`, `OC`, `key`, `token`, or `secret`.

## Sanitized Summary Policy

Seeds store only a short sanitized summary and source anchor/reference metadata. Full MOLEG JSON/XML and full article body text must not be stored in seed/manual evidence.

## Validation

```bash
python -m scripts.validate_official_law_seeds
```

Use `--include-examples` to include the dummy example file.

## Import

```bash
python -m scripts.import_official_law_seeds
```

The importer validates first. Invalid seeds stop import. Empty valid files are skipped. Imports are idempotent by document/article/candidate keys.

## Candidate Check

After import, check:

```text
GET /api/legal-references/official-law-seeds/status
GET /api/legal-references/procedure-article-candidates?source_mode_detail=official_seed_db
GET /api/legal-references/official-law-snapshot
```

## Analyze Behavior

`/api/analyze` keeps 13 procedures. When no official seed article exists, existing fallback behavior remains: `procedure_keyword_candidate` or review-needed. When reviewed seed articles exist, `official_seed_db` candidates are preferred. Confirmed seed candidates are surfaced as confirmed references.

## Future MOLEG Live Comparison

When MOLEG live transport is stable, compare live normalized metadata against manual seeds by law key, article anchor, article number, title, effective date, and source timestamp. Differences should be flagged for review; live data should not silently overwrite reviewed seeds.
