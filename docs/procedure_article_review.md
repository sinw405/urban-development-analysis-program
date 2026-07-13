# Procedure Article Review Workflow

Phase 39 adds a reviewer-driven workflow for procedure to official article candidates. The workflow does not automatically confirm legal basis mappings.

## Candidate Meaning

A candidate is a possible link between a procedure step and an official law article. Candidates can be generated from official DB keyword matching, manual seed data, or reviewed seed data. A candidate is not a confirmed legal basis until a reviewer explicitly confirms it.

## Statuses

- `unconfirmed`: generated candidate that needs human review.
- `confirmed`: reviewer approved the candidate with reviewer and note.
- `rejected`: reviewer decided the candidate is not a direct basis.
- `needs_revalidation`: candidate was confirmed under one MST but the current stored live MST differs.
- `stale`: confirmed candidate points to an article that is no longer available.

The current schema stores the latest review state in `is_confirmed`, `confirmed_at`, `confirmed_by`, `confirmed_source`, and `confirmation_note`. `confirmed_source` is used to distinguish `manual_review_confirmed`, `manual_review_rejected`, and `manual_review_reopened`. The note appends review transitions so the latest field still preserves the previous and new status text.

## CLI

List candidates:

```powershell
python -m scripts.procedure_article_review list --status unconfirmed
```

Show candidate detail, including normalized DB article text:

```powershell
python -m scripts.procedure_article_review show --candidate-id <ID>
```

Confirm requires reviewer and note:

```powershell
python -m scripts.procedure_article_review confirm --candidate-id <ID> --reviewer "<reviewer>" --note "<confirmed basis>"
```

Reject requires reviewer and note:

```powershell
python -m scripts.procedure_article_review reject --candidate-id <ID> --reviewer "<reviewer>" --note "<reject reason>"
```

Reopen requires reviewer and note:

```powershell
python -m scripts.procedure_article_review reopen --candidate-id <ID> --reviewer "<reviewer>" --note "<reopen reason>"
```

Reviewer and note are mandatory for all mutation commands. Missing candidates, missing reviewers, and missing notes fail without changing DB state.

## Candidate Refresh Policy

Candidate refresh must preserve human review decisions:

- confirmed remains confirmed
- rejected remains rejected
- review note is not cleared
- duplicate candidates are not created for the same procedure/article/source identity
- new candidates start as unconfirmed
- code does not automatically approve candidates after refresh

## Analyze API Rules

`/api/analyze` keeps 13 procedures and existing order. Unconfirmed candidates are not returned as verified legal basis. Confirmed candidates are appended to `legal_references` with `reference_quality=verified` only when they are still applicable. Rejected candidates are excluded. Candidates requiring revalidation set the step reference state to `needs_revalidation` instead of being treated as confirmed.

## Version Change Handling

A confirmed candidate records the MST present at confirmation time through the candidate `mst` field. At read time, the service compares that MST with the latest stored live document MST for the same official law ID.

- Same MST: confirmed candidate can be used.
- Different MST: `needs_revalidation`.
- Missing article: `stale`.
- Before available history: not applicable as a confirmed basis for that as-of date.

The service does not infer that a changed MST remains legally equivalent.

## Official URL

The detail command uses the stored sanitized official source URL when available. If the project cannot provide a trustworthy official URL, it returns:

```json
{"official_url": null, "official_url_status": "unavailable"}
```

It must not invent a URL from guessed law or article identifiers.

## Safety

- No unauthenticated mutation HTTP endpoint is added.
- API keys and OC values are not printed.
- Raw MOLEG XML/HTML is not stored or displayed.
- Test fixtures use dummy IDs only.
- Real live candidates are not automatically confirmed.

## Recovery

If a candidate was confirmed or rejected in error, run `reopen` with a reviewer and reason. The candidate returns to unconfirmed review state and can be reviewed again.