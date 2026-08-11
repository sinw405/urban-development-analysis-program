# Phase 45 ? Procedure graph and legal-basis baseline audit

## Scope

Phase 45 audits the existing S2/T2.1 rule engine and adds only the missing standard procedure graph. It does not replace the existing detailed workflow, fabricate legal articles or thresholds, add Baekhyeon MICE-specific behavior, or introduce Phase 46 functionality.

## Baseline audit

| Area | Baseline | Phase 45 result | Evidence |
|---|---|---|---|
| A. Standard urban-development procedure | PARTIAL | COMPLETE | Detailed steps existed; `standard_procedure_graph` now defines the required six stages. |
| B. Procedure-step model | COMPLETE | COMPLETE | YAML steps and `ProcedureStep` response schema are reused. |
| C. Order and dependencies | PARTIAL | COMPLETE | Existing `sequence` is preserved; standard and detail dependencies are now explicit and validated. |
| D. Legal-basis mapping | PARTIAL | PARTIAL | `ProcedureLegalReference` supports law/article mapping; unverified production mappings remain candidate/missing rather than fabricated. |
| E. As-of law version linkage | COMPLETE | COMPLETE | Analyze API reuses `get_article_versions(..., as_of=...)` and returns current/scheduled article versions. |
| F. Expropriation/replotting/mixed branches | COMPLETE | COMPLETE | Existing external rules and aliases are preserved and mapped into the standard graph. |
| G. Public/private/public-private SPC branches | COMPLETE | COMPLETE | Existing implementer rules are preserved and mapped into the standard graph. |
| H. Assessment determination | PARTIAL | PARTIAL | Assessment candidates exist, but thresholds remain explicit non-production placeholders pending verified legal criteria. |
| I. External rule configuration | COMPLETE | COMPLETE | Procedure and assessment rules remain in YAML. |
| J. Analyze service/API | COMPLETE | COMPLETE | Existing `/api/analyze` path is reused; graph fields are additive. |
| K. Rule validation | MISSING | COMPLETE | Graph codes, dependencies, and complete one-to-one detail mapping are validated. |
| L. Regression/snapshot coverage | PARTIAL | PARTIAL | Rule/API/as-of regression exists and Phase 45 graph tests were added; no dedicated serialized snapshot suite is introduced. |

## Standard and detailed graph

The stable standard order is:

1. `ZONE_DESIGNATION_PROPOSAL` ? 구역지정 제안
2. `ZONE_DESIGNATION_NOTIFICATION` ? 구역 지정·고시
3. `DEVELOPMENT_PLAN` ? 개발계획
4. `IMPLEMENTATION_PLAN_AUTHORIZATION` ? 실시계획 인가
5. `PROJECT_IMPLEMENTATION` ? 사업시행
6. `COMPLETION` ? 준공

Each standard stage contains the selected existing detailed step codes. Existing common and conditional steps are neither removed nor renamed. The analyze response exposes `standard_procedure_graph`; each detailed procedure exposes its `standard_stage_code`, `standard_stage_name`, and `depends_on` relationship.

## Legal basis and as-of behavior

No law name, article number, or threshold was added. Standard stages use `legal_basis_status: unresolved`. Detailed steps retain their existing placeholders and are enriched only from stored `ProcedureLegalReference` rows. When an analysis supplies `as_of`, the existing law/article/article-version service selects the temporal article version and returns it under `legal_references.current_version` and `versions`.

## Compatibility and data model

The existing analyze endpoint, branch rules, persistence, candidate review, and law-version models are reused. The response change is additive. No database migration or new endpoint is required.

## Known limitations

Verified article mappings and assessment thresholds remain incomplete and require actual MOLEG-ingested data plus expert review. The assessment YAML's legacy text encoding should be corrected in a separate scoped maintenance phase; its placeholder semantics are unchanged here. A dedicated snapshot suite remains future work.
