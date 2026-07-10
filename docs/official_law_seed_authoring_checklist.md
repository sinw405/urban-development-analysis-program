# Official Seed Authoring Checklist

Use this checklist before adding real official seed articles.

## Source Review

- Confirm the source is an official source.
- Confirm `law_name` exactly from the official source.
- Confirm `article_no` exactly from the official source.
- Confirm `article_title` exactly from the official source.
- Record an `article_anchor` or official URL without secret query parameters.
- Confirm effective date and promulgation date when relevant.

## Procedure Mapping

- Confirm the target `procedure_code` exists in project rules.
- Explain why the article is connected to that procedure in `sanitized_summary` or `confirmation_note`.
- Do not infer review requirements, thresholds, or legal conclusions from memory.

## Sanitization

- Do not store full article body text.
- Do not store raw MOLEG JSON or XML.
- Do not store `serviceKey`, `OC`, token, secret, or API key values in URLs.
- Use a short sanitized summary that describes why the article was selected.

## Confirmation

Set `is_confirmed=true` only when:

- the source is official,
- article number/title/anchor have been checked,
- the procedure mapping has been reviewed,
- `verified_by` or `confirmation_note` is present.

Use a second reviewer when the mapping affects an external report, legal-risk decision, or final deliverable.

## Commands Before Import

```bash
python -m scripts.validate_official_law_seeds
python -m scripts.import_official_law_seeds --dry-run
python -m scripts.import_official_law_seeds
```

For fixture or staging directories:

```bash
python -m scripts.validate_official_law_seeds --path tests/fixtures/official_law_seeds
python -m scripts.import_official_law_seeds --path tests/fixtures/official_law_seeds --dry-run
```