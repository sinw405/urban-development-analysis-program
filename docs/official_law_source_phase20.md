# Phase 20 Official Law Source Preparation

## Purpose

Phase 20 prepares the backend structure for future official legal text integration. It does not call the MOLEG Open API, the National Law Information Center, or any other external network service.

The current Phase 18 and Phase 19 legal references are TEST seed based candidate references. Phase 20 adds a preview layer that can compare those candidate references with an official-source-shaped provider and report whether each candidate may later be promoted to verified.

## Why An Adapter Is Needed Before Real MOLEG Integration

Official legal data integration needs a stable boundary before API credentials, request formats, throttling, and source data quirks are introduced. The adapter boundary lets the application test matching and promotion logic without depending on external network availability or API keys.

This keeps the existing analyze API stable while future provider implementations can be swapped behind the same interface.

## LawSourceProvider Structure

`LawSourceProvider` is defined as a protocol with these methods:

```text
get_article_by_law_and_article(law_name, article_number_text)
get_law_metadata(law_name)
search_articles(law_name=None, keyword=None)
```

The provider returns official-source-shaped snapshots containing law name, article number, title, text, effective date, source URL, and source type.

## Mock Official Source Role

`MockOfficialLawSourceProvider` implements the provider interface with in-process fixture data only. It returns `source_type: mock_official` and placeholder URLs under `https://mock.official.local/`.

The mock source is intentionally not authoritative. Its role is to make verification preview behavior testable before a real MOLEG or National Law Information Center adapter exists.

## Candidate To Verified Flow

Phase 20 only evaluates promotion possibility:

```text
candidate legal reference
-> LawSourceProvider lookup
-> verification_result preview
-> expert or authority review later
-> verified promotion in a future phase
```

No Phase 20 code changes stored candidate references to verified. Existing `candidate`, `verified`, and `missing` quality semantics remain unchanged.

## Match Status Definitions

`matched` means the candidate law name and article number matched a provider article, the candidate article title or keyword overlapped with official title/text, and a source URL exists. This returns `can_promote_to_verified: true` as a preview only.

`partial` means the law name and article number matched, but another required signal such as title/keyword overlap or source URL was missing. This returns `can_promote_to_verified: false`.

`unmatched` means the provider could not find an article for the candidate law name and article number, or the candidate lacks required lookup fields. This returns `can_promote_to_verified: false`.

## Preview API

Phase 20 adds an internal development endpoint:

```text
POST /api/legal-references/verify-preview
```

Request body:

```json
{
  "procedure_reference_ids": [1, 2, 3]
}
```

If `procedure_reference_ids` is omitted, the endpoint evaluates all stored procedure legal references. The endpoint returns preview results and does not mutate the database.

## Future Real MOLEG Integration Tasks

A future phase should add a real provider implementation that handles official API authentication, request signing or parameters, pagination, rate limits, source-specific identifiers, response normalization, retries, and error handling.

The real provider should preserve raw official payload snapshots, capture source URLs or official document identifiers, support effective-date lookup, and store enough evidence for audit and expert review.

## Practical Cautions

Do not treat `mock_official` as legal evidence. A `matched` preview is not the same as a reviewed verified reference.

Before promoting any reference to verified, confirm the official legal text, article number and title, effective date, procedure applicability, permitting authority interpretation, and expert review evidence.

Do not use real API keys, external network calls, or automated verified promotion in this phase.
