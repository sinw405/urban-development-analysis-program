# Phase 61 — Reference disclaimer and final verification guidance (T6.3)

## Source and scope

The project workbook `12.도시개발사업 관련 분석 프로그램.xlsx` requires reference-only notices, original-law links and final confirmation through the permitting authority and expert advice. The guidebook `도시개발_분석프로그램_개발가이드북_체크리스트.html`, S6 item `t63`, requires stating that analysis is reference material rather than an authoritative legal interpretation, with notices on every screen. Both original local files were read for this phase. No external web sources or legal interpretations were used.

T6.3 changes frontend presentation only. Backend/API schemas, the rule engine, case registration and Phase 60 monitoring/backup contracts remain unchanged. T6.4 ordinance fallback is outside this phase.

## Actual UI coverage

`src/main.tsx` renders `App.tsx`. The custom history router in `src/router.ts` has `/`, `/analyze`, `/analyses`, `/analyses/:id` and `/law-updates`. `App` renders one global `ReferenceDisclaimer` inside `main`, before all route content, including loading/error states. Unknown paths retain the existing dashboard fallback; malformed analysis IDs retain the existing shell. There is no separate not-found, law-detail, case-comparison or case-registration route.

`AnalysisResult` is shared by submitted and saved analysis results. Its detailed notice precedes the summary, case comparison, procedure roadmap/detail, assessment checklist and RAG explanation. `AnalysisReport` reuses the same component for its printed-report notice. Existing candidate-reference and case-comparison cautions remain intact.

The component keeps the reference-only, non-authoritative, original-source verification, permitting-authority confirmation and expert guidance text in one place. It does not claim legal effect, guaranteed accuracy, institutional approval or completed expert review. It contains no generated URLs. Existing RAG `officialSourceUrl` validation and conditional original-law anchors, including law-update links, are unchanged. Missing original links are explicitly addressed in the detailed guidance.

## Accessibility and responsive presentation

The notice is a semantic `aside`, named by an actual heading using React `useId`. Text is visible without expanding a dialog; no alert/live region or color-only warning is used. There are no new focus controls or external counseling links. Existing source links remain keyboard operable.

Notice text wraps at small widths and stays in normal document flow. The shared `.stack` single grid column uses `minmax(0, 1fr)` so existing result tables can scroll inside their wrappers instead of forcing the surrounding notice beyond a mobile viewport. Print styling keeps the report notice visible.

## Verification commands

From `frontend/`:

```powershell
npm ci
node scripts/phase61-ui-contract.mjs
node scripts/phase54-ui-contract.mjs
node scripts/phase55-ui-contract.mjs
node scripts/phase56-ui-contract.mjs
npm run typecheck
npm run build
```

There is no existing package test or lint script. Phase 61 follows the existing Node assertion-script convention and adds actual React rendering to its 14 checks. Older contract checks cover RAG/source/checklist and case-comparison integration.

Optional browser verification uses a local Chrome installation and Playwright Core in the Git-ignored `backups/` tool directory. From the repository root, install only the optional tool:

```powershell
npm install --prefix backups/phase61-tools --no-save --package-lock=false playwright-core
```

Run `npm run dev -- --host 127.0.0.1` from `frontend/` in a separate terminal, then run `node scripts/phase61-browser.mjs` there. `PHASE61_UI_URL` can override the default `http://127.0.0.1:5173` address. Browser verification uses explicit TEST API fixtures and the existing Phase 55 stored-source URL fixture; it never submits to a real backend or visits a real law page. Screenshots go to `backups/phase61-visual/`.

Observed browser result: 31 checks passed at widths 1440, 768, 360 and 320 pixels. Checks cover every actual route plus existing malformed-ID/dashboard fallback states, form submission, saved results, procedure/detail, assessment, case selection, RAG provided/missing source, keyboard activation of an original-source link, print notice and an API error state. Desktop/mobile screenshots were visually inspected. These are actual frontend runtime checks with mocked API data, not live law-data acceptance tests.

Phase 56–60 backend regression passed: 45 tests (33 Phase 56–59 plus 12 Phase 60). Prior actual backup and isolated restore validation results remain valid; this UI phase does not rerun those jobs.
