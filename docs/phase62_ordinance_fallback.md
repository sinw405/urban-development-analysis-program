# Phase 62 — Municipality ordinance variance and standard fallback (T6.4)

## Source of truth

The original local workbook `12.도시개발사업 관련 분석 프로그램.xlsx` calls for reflecting municipal ordinances when available and providing standard procedures otherwise. The guidebook `도시개발_분석프로그램_개발가이드북_체크리스트.html`, S6 `t64`, requires variance guidance and fallback for unlinked municipalities. Both original files were read. No external web search, municipality-specific legal interpretation, threshold, document requirement or processing time was added.

## Actual data and availability

`AnalyzeRequest` and `Project` have free-text `location` and `local_government` fields. There is no separate sido/sigungu selector, municipality coverage lookup, verified municipality ordinance dataset, ordinance model, integration service or ordinance availability field in the analysis response. Existing `local_rule_required` assessment flags indicate that local rules require confirmation; they do not demonstrate that an ordinance was collected or applied.

The UI therefore exposes only the current system capability `not_linked` (조례 미연동). This is not a statement that a municipality has no ordinance. Region names do not imply availability. Available and unknown municipality-specific states are not fabricated; there is no evidence-backed way to distinguish them in this repository. The production-usable municipal ordinance coverage is none. TEST/mock data is used only by tests.

## Standard fallback behavior

The existing analyzer already selects common and standard procedure candidates from repository YAML, independent of municipality names. Lack of ordinance data is not an exception or HTTP 500 condition. Phase 62 keeps that behavior and labels its meaning explicitly: results use currently registered common legal references and standard procedures, are not the municipality's final procedure, and preserve missing/candidate/expert-review states. Standard fallback does not promote draft procedures or placeholder assessment criteria to verified legal determinations.

No backend production code, API schema, database migration, rule configuration, ordinance source URL or case schema is changed. Real analysis validation/API errors keep their original error semantics; they are not replaced by synthetic successful results.

## UI coverage

`MunicipalityOrdinanceNotice` owns the reusable wording and named semantic `aside`. `App` shows a compact global notice on every existing route, including loading/error/fallback states. `AnalysisForm` shows input-context guidance using the entered `local_government`. `AnalysisResult`, shared by newly submitted and saved results, shows detailed guidance before summary, case comparison, procedure/detail and assessment outputs. It uses the result's region, not a subsequently edited input value. `AnalysisReport` retains the same guidance in print output.

The wording states that local ordinances and committee operating criteria may change procedures, reviews, documents and handling, that integration is absent, and that actual application requires checking municipal self-governing regulations and the permitting authority. No source link is generated. Existing original-law links and Phase 61 `ReferenceDisclaimer` remain unchanged.

Notices stay in normal document flow, use actual headings and text rather than color-only status, and introduce no modal or keyboard controls. Text wraps at small widths. The report's single grid track uses `minmax(0, 1fr)` so a table's minimum width cannot clip the notices inside the existing report container. Checklist text also wraps long existing placeholder values such as `TODO_EXPERT_REVIEW` to prevent horizontal overflow at 320 pixels without changing their meaning.

## Validation

From `frontend/`:

```powershell
node scripts/phase62-ui-contract.mjs
node scripts/phase54-ui-contract.mjs
node scripts/phase55-ui-contract.mjs
node scripts/phase56-ui-contract.mjs
npm run typecheck
npm run build
```

Phase 62's React-rendering contract script reuses the Phase 61 harness and executes its 14 regression checks, then performs 15 Phase 62 checks. The repository has no lint script; no new lint infrastructure is introduced.

For optional Chrome verification, reuse the Phase 61 local Playwright Core tool installation described in `phase61_reference_disclaimer.md`, run `npm run dev -- --host 127.0.0.1`, then `node scripts/phase62-browser.mjs`. It first runs all 31 Phase 61 browser checks and adds 34 Phase 62 checks at 1440×1000, 768×1024, 360×800 and 320×800. The checks cover all real routes, unlinked input/new/saved results, region isolation after editing, procedures/assessments, case selection, print, preserved disclaimer and genuine analysis/detail API errors. TEST API interception prevents real database writes and external ordinance calls. Screenshots are Git-ignored under `backups/phase62-visual/`.

Backend verification uses `tests/test_phase62_ordinance_fallback.py` plus the Phase 56–60 suites. Five new checks use an in-memory SQLite database and the actual analyze/save/detail endpoints, with law-data enrichment stubbed. They verify standard results and local-rule-required flags for unlinked/empty region names, saved-payload preservation, unchanged rule outputs across regions, and HTTP 422 for invalid input. No production/application database is used. Together with the 45 Phase 56–60 regression tests, 50 tests pass.

## Limits and stage status

T6.4 addresses guidance and standard fallback for unlinked municipalities. Actual municipal ordinance collection, coverage metadata, version verification and locality-specific rules remain future work and must use verified sources. This limitation does not prevent completion of the guidebook's unlinked fallback requirement.

Existing statuses remain: T5.1 PARTIAL; T5.2 NOT STARTED / DEFERRED; T5.3 COMPLETE; T6.1 PARTIAL (external production deployment not verified); T6.2 COMPLETE; T6.3 COMPLETE. Phase 62 does not claim that the whole project is complete.
