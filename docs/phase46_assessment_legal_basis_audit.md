# Phase 46 - Assessment and legal-basis audit

## Scope and evidence policy

This audit covers the assessment output of `POST /api/analyze`, the external assessment rule configuration, stored `ProcedureLegalReference` rows, and the existing law/article/article-version as-of lookup. No law name, article number, numeric threshold, or project-specific criterion was inferred. PostgreSQL contained zero assessment-code legal references at the start of Phase 46, so no production assessment could be promoted to VERIFIED.

## Baseline audit and Phase 46 classification

| Assessment | Code | Baseline | Phase 46 | Condition / required input | Threshold | Governing law/article | As-of | Baseline test |
|---|---|---|---|---|---|---|---|---|
| Urban planning committee review | `URBAN_PLANNING_COMMITTEE_REVIEW` | PARTIAL | UNRESOLVED | Condition unverified; `urban_planning_review_context` | Placeholder only | No stored assessment reference | Supported when stored | Procedure regression only |
| Environmental impact assessment | `ENVIRONMENTAL_IMPACT_ASSESSMENT` | PLACEHOLDER | PLACEHOLDER | Condition unverified; `environmental_assessment_context` | Placeholder only | No stored assessment reference | Supported when stored | Placeholder regression |
| Traffic impact assessment | `TRAFFIC_IMPACT_ASSESSMENT` | PLACEHOLDER | PLACEHOLDER | Condition unverified; `traffic_assessment_context` | Placeholder only | No stored assessment reference | Supported when stored | Placeholder regression |
| Disaster impact review | `DISASTER_IMPACT_REVIEW` | NOT_IMPLEMENTED | UNRESOLVED | Condition unverified; `disaster_review_context` | Placeholder only | No stored assessment reference | Supported when stored | None |
| Landscape review | `LANDSCAPE_REVIEW` | NOT_IMPLEMENTED | UNRESOLVED | Condition unverified; `landscape_review_context` | Placeholder only | No stored assessment reference | Supported when stored | None |
| Educational environment review | `EDUCATIONAL_ENVIRONMENT_REVIEW` | NOT_IMPLEMENTED | UNRESOLVED | Condition unverified; `educational_environment_context` | Placeholder only | No stored assessment reference | Supported when stored | None |
| Underground safety assessment | `UNDERGROUND_SAFETY_ASSESSMENT` | PLACEHOLDER | PLACEHOLDER | Condition unverified; `underground_safety_context` | Placeholder only | No stored assessment reference | Supported when stored | Placeholder regression |
| Buried cultural heritage review | `BURIED_CULTURAL_HERITAGE_REVIEW` | PLACEHOLDER | PLACEHOLDER | Condition unverified; `buried_heritage_context` | Placeholder only | No stored assessment reference | Supported when stored | Placeholder regression |

## Result semantics

Assessment legal evidence and applicability are deliberately independent:

- `legal_basis_status`: `verified`, `candidate`, `unresolved`, `placeholder`, or `missing`.
- `determination_status`: `NEED_MORE_INFO` when configured inputs are absent; otherwise `UNRESOLVED` while the condition remains unverified.
- `REQUIRED` and `NOT_REQUIRED` are not emitted by the current configuration because no verified applicability condition or threshold exists.
- `missing_inputs` identifies the absent assessment context without inventing a threshold.

The legacy `name`, `status`, `threshold`, `legal_basis`, `required_action`, and `notes` fields remain. New fields are additive.

## Verified legal-reference linkage

No production assessment reference was found or added. The analyze API now queries existing `ProcedureLegalReference` rows using the assessment code. A stored verified reference is serialized through the existing law/article relationship, and `get_article_versions(..., as_of=...)` selects the current and scheduled article versions. Candidate references remain candidate. A verified legal reference does not by itself prove that an assessment is required.

## Rule configuration and validation

`rules/assessment_rules.yaml` remains the external configuration source. It expresses code, name, condition, required inputs, placeholder threshold, legal basis, and legal-basis status. Validation rejects duplicate codes, malformed required-input lists, unsupported statuses, and attempts to label a placeholder legal basis as verified.

## Regression coverage

Phase 46 tests use names containing `TEST` and `DO_NOT_USE`; they are fixtures, not production legal data. Coverage includes missing evidence, placeholder rules, missing inputs, verified stored-reference enrichment, as-of version selection, rule validation, stable serialized assessment matrices, existing implementation-method branches, implementer branches, and API compatibility.

## Known limitations

Actual applicability conditions, governing statutes, articles, and numeric thresholds remain unresolved. They require verified MOLEG-ingested records and expert-reviewed rule configuration. This phase does not add an assessment-specific database table; it intentionally reuses `ProcedureLegalReference`. No Live MOLEG request was made.
