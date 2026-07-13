# Law Change Impact Workflow

Phase 40 connects stored MOLEG law version diffs to procedure-article review candidates.

## Scope

This workflow does not interpret the legal meaning of an amendment. It only records structural article changes and whether those changed articles are connected to confirmed mappings or unconfirmed/rejected candidates.

## Version Diff vs Impact

`moleg_version_diff_service` compares two stored live `OfficialLawDocument` rows by law name and MST. Article identity is based on law ID plus article number and source anchor when available. Content changes are detected from normalized article title and body hashes, so an MST change alone does not mark every article changed.

`LawVersionImpactService` takes that diff and derives system review work:

- `confirmed + unchanged`: no review event is generated.
- `confirmed + changed`: derived status is `needs_revalidation`; the previous confirmation remains stored.
- `confirmed + removed`: derived status is `stale`; the previous confirmation remains stored but is not exposed as current legal basis.
- `unconfirmed + changed/removed`: remains unconfirmed; no auto-confirm.
- `rejected`: remains rejected; no auto-reopen.
- `added`: may create or preview only unconfirmed candidates from existing candidate rules.

## Impact Levels

Impact level is system review priority, not legal importance.

- `high`: confirmed article changed or removed.
- `medium`: unconfirmed candidate changed/removed, or added article generated a new unconfirmed candidate.
- `informational`: no connected mapping/candidate, or unchanged.

## State Propagation

Phase 40 uses derived status. Candidate confirmation rows are not overwritten to `needs_revalidation` or `stale`. Review history and the original confirmation fields remain intact. `/api/analyze` suppresses confirmed legal references when the latest impact event for that candidate is `needs_revalidation` or `stale`.

## Review History

`procedure_article_review_events` is append-only for confirm/reject/reopen actions. Each event stores previous status, new status, reviewer, note, reviewed_at, reviewed MST, reviewed effective date, candidate ID, and source. The older `confirmation_note` text chain is retained for backward compatibility.

## Impact Events

`law_change_impact_events` stores one event per idempotency key:

`law ID + from MST + to MST + stable article ID + candidate ID or none + change type`

The table stores hashes, article identifiers, affected procedure, mapping status, derived review status, impact level/reason, provenance, official URL status, and safe metadata. Raw XML/HTML and full MOLEG payloads are not stored.

## CLI

Dry-run is the default analysis path:

```bash
python -m scripts.moleg_change_impact analyze --law-name "도시개발법" --from-mst 284059 --to-mst 284059
```

Apply persists impact events in one transaction:

```bash
python -m scripts.moleg_change_impact apply --law-name "도시개발법" --from-mst 284059 --to-mst 284059
```

List and show:

```bash
python -m scripts.moleg_change_impact list --status needs_revalidation
python -m scripts.moleg_change_impact show --event-id 1
```

`--force-rollback` is test-only and verifies transaction rollback.

## Source Priority

The current candidate service sorts and filters by:

1. `official_seed_db`
2. `official_manual_db`
3. `official_db` including confirmed procedure-article mappings
4. `fixture_only`
5. no candidate / `needs_review`

Confirmed candidates are still required before `/api/analyze` exposes a legal reference. Unconfirmed and rejected candidates are not exposed as confirmed legal basis.

## API and UI

`GET /api/law-updates` returns legacy update events and Phase 40 impact events. `GET /api/updates` is a read-only alias. Impact rows distinguish:

- `confirmed mapping impact`
- `unconfirmed candidate impact`
- `unmapped law change`

The LawUpdates screen is read-only. It shows law name, changed article, change type, from/to MST or effective date, affected procedure, impact level, review status, official URL status, and detected time.

## Historical Version Limitation

Live MOLEG ingest currently stores one operational version per target law. Real live validation may only prove same-MST unchanged behavior and idempotency. Changed/removed/added behavior is verified with test fixtures and rollback transactions, not by inserting fake operational law data.

## Recovery

Impact apply runs in a transaction. If an exception occurs, no partial impact events are committed. Candidate confirmation data is not deleted or reset by impact processing. Human reviewers must explicitly reopen or reconfirm with reviewer and note.
