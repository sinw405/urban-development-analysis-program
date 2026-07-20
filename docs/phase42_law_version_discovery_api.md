# Phase 42 Law Version Discovery API

## Purpose

Phase 42 stabilizes MOLEG eflaw version discovery for law search responses that span multiple pages. It collects every page, filters exact law-title matches, selects the latest/current version and the immediately previous effective version deterministically, and connects the selected MST pair to the existing law-change impact service and FastAPI router.

This phase does not automatically persist API responses or create database update events. Event persistence is reserved for the next phase.

## Pagination

`discover_law_versions()` sends the first search request with `target=eflaw`, `display=100`, and `page=1`. It reads `totalCnt`, `page`, `numOfRows`, `resultCode`, `resultMsg`, and `law` items. When `totalCnt` is larger than the first page size, it requests the remaining pages and merges all items.

Safety limits and failure behavior:

- Default max pages: `20`
- Default max items: `1000`
- Total-page calculation is based on the first page row count, so a shorter last page does not trigger an extra request.
- A non-success `resultCode` returns a source error.
- An empty intermediate page returns `empty_intermediate_page`.
- Missing MST items are skipped with a warning.
- Malformed MST values are kept but recorded as warnings.
- Duplicate MST items are deduplicated by MST, keeping the item with the highest parsed sort key.
- API keys and full secret-bearing URLs are never emitted.

## Law Name Normalization

Law names are compared after trimming, collapsing repeated whitespace, and casefolding. XML CDATA text is handled by the XML parser before normalization.

Allowed examples:

```text
Urban Development Act
 Urban Development Act
<![CDATA[ Urban Development Act ]]>
```

Rejected examples:

```text
Urban Development Act Enforcement Decree
Urban Development Act Enforcement Rule
Special Act on Enterprise City Development
```

For the Korean live target, this means the exact title for the Urban Development Act is accepted, while its enforcement decree, enforcement rule, and similarly named statutes are rejected.

## Version Sorting And Selection

Versions are sorted by parsed values, not raw strings:

1. Effective date
2. Promulgation date
3. MST number

Sorting is descending. `select_latest_version_pair()` chooses the first sorted version as `to_version` and the next older version from the same law-id family as `from_version`. If no previous version exists, it returns `None`; it does not fall back to an arbitrary first item.

The selection payload includes:

- `law_name`
- `from_mst`, `to_mst`
- `from_promulgation_date`, `to_promulgation_date`
- `from_effective_date`, `to_effective_date`
- `from_history_status`, `to_history_status`
- `selection_reason`

## Automatic Versus Manual MST Selection

Automatic mode is used when `from_mst` and `to_mst` are omitted. Discovery selects the latest/current pair and passes that pair to `LawVersionImpactService.analyze()`.

Manual mode is used when both MST values are provided. Manual values take priority, with validation:

- Identical `from_mst` and `to_mst` are rejected.
- If discovery can resolve both MSTs and `from_mst` is newer than `to_mst`, the request is rejected.
- Providing only one MST is rejected.
- If a manual MST is not found in discovery, date order cannot be verified; the pair is still passed to the DB-backed impact service, which returns `missing_version` if stored documents are unavailable.

## FastAPI Endpoint

Endpoint:

```http
POST /api/law-updates/live-impact
```

Automatic request:

```json
{
  "law_name": "Urban Development Act",
  "dry_run": true
}
```

Manual request:

```json
{
  "law_name": "Urban Development Act",
  "from_mst": "276975",
  "to_mst": "284059",
  "dry_run": true
}
```

Response shape:

```json
{
  "law_name": "Urban Development Act",
  "source": "MOLEG",
  "status": "ok",
  "selection_mode": "auto",
  "selection_reason": "sorted_by_effective_date_promulgation_date_mst_desc",
  "from_version": {
    "mst": "276975",
    "promulgation_date": "2025-10-01",
    "effective_date": "2026-01-02",
    "status": "history"
  },
  "to_version": {
    "mst": "284059",
    "promulgation_date": "2026-03-05",
    "effective_date": "2026-07-01",
    "status": "current"
  },
  "changed": true,
  "changed_articles": [],
  "impacted_rules": [],
  "warnings": [],
  "errors": [],
  "checked_at": "2026-07-20T00:00:00Z",
  "discovery": {
    "status": "ok",
    "total_count": 188,
    "page_count": 2,
    "requested_pages": [1, 2],
    "collected_item_count": 188,
    "exact_match_count": 69,
    "distinct_mst_count": 69
  },
  "secret_exposed": false
}
```

If the selected documents are not already stored in the DB, the endpoint returns a structured `missing_version` result with `version_not_available`. It does not fabricate mock impact results.

## Live Verification

Normal pytest runs do not call the external MOLEG API. Run live discovery only in a local environment with credentials configured:

```powershell
python scripts/moleg_live_change_e2e.py discover --law-name <exact law name> --max-versions 50
```

To verify DB-backed diff and impact, first persist the selected live versions through the existing ingest flow:

```powershell
python scripts/moleg_live_change_e2e.py run --law-name <exact law name> --apply-ingest
```

## Environment Variables

Example `.env` keys:

```text
MOLEG_API_ENABLED=true
MOLEG_LIVE_TEST_ENABLED=true
MOLEG_API_BASE_URL=https://www.law.go.kr
MOLEG_API_KEY=<local secret only>
```

`MOLEG_OC` may also be used as the key alias. Never put a real key in source code, tests, docs, logs, or API examples.

## Secret Handling

- `OC`, `MOLEG_API_KEY`, `MOLEG_OC`, and `serviceKey` are redacted in URLs and payloads.
- Fixtures use test-only placeholder secrets.
- Live verification output omits key values and full secret-bearing URLs.
- Error results keep `secret_exposed=false` when no secret appears in the response.

## Known Limits

- Impact analysis remains DB-backed. Live discovery alone is not enough to diff laws unless both selected MST documents are stored.
- Exact-title matching can include historical law-id families with the same title. Pair selection requires the latest and previous versions to belong to the same law-id family when law IDs are present.
- API response persistence and update-event persistence are outside Phase 42.

## Next Phase

The next phase should persist selected live pair checks and impact results as auditable DB events with idempotency and operator review metadata.