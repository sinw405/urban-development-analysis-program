# Phase 17 Legal Data Coverage

## Scope

Phase 17 improves the first layer of legal-data coverage for core procedure display without adding real legal article mappings, final criteria, new database schema, server PDF generation, or automatic legal-text collection.

## Data Creation Locations Checked

```text
rules/procedure_rules.yaml: procedure step candidates, required document candidates, agency candidates, duration placeholders, legal basis placeholders
backend/app/services/analyzer.py: converts procedure rules into result_payload procedures
backend/app/services/legal_reference_service.py: attaches procedure_legal_references to procedure steps by step_code
backend/app/services/dev_seed_service.py: creates TEST-only law, article, versions, procedure legal reference, and law update event
backend/app/models/law.py: laws table model
backend/app/models/law_article.py: law_articles table model
backend/app/models/law_article_version.py: law_article_versions table model
backend/app/models/procedure_legal_reference.py: procedure_legal_references table model
frontend/src/utils/analysisSummary.ts: normalizes result_payload for roadmap, detail, report, and missing-data display
frontend/src/components/ProcedureRoadmap.tsx: displays ordered procedure roadmap
frontend/src/components/ProcedureStepDetail.tsx: displays step-level details and legal references
frontend/src/components/AnalysisReport.tsx: displays report summary and coverage counts
```

## Current Result Payload Fields

Each procedure step currently exposes:

```text
step_code
step_name
sequence
description
required_documents
related_agencies
estimated_duration
legal_basis_placeholder
legal_references
notes
```

Legal references currently expose IDs, keys, mapping statuses, placeholder/status values, version metadata, source, and notes. The frontend does not receive a verified article URL field in Phase 17.

## Core Procedure Coverage

Phase 17 adds a common placeholder workflow step for implementer designation review:

```text
IMPLEMENTER_DESIGNATION_REVIEW
```

This fills a workflow coverage gap between development plan establishment and implementation plan authorization. It intentionally keeps required documents, related agencies, duration, and legal article reference as confirmation-required placeholders.

Core common procedure candidates after Phase 17:

```text
PROJECT_BASIC_REVIEW
ZONE_DESIGNATION_REVIEW
RESIDENT_OPINION_HEARING
RELATED_AGENCY_CONSULTATION
URBAN_PLANNING_COMMITTEE_REVIEW
ZONE_DESIGNATION_NOTIFICATION
DEVELOPMENT_PLAN_ESTABLISHMENT
IMPLEMENTER_DESIGNATION_REVIEW
IMPLEMENTATION_PLAN_AUTHORIZATION
PROJECT_IMPLEMENTATION
COMPLETION_INSPECTION
```

## Coverage Summary

```text
Core common procedure candidate count: 11
TEST legal reference connected step count through demo seed: 1
Legal reference connected step: PROJECT_BASIC_REVIEW
Legal reference unconnected core step count: 10
Steps with required document candidates: 10
Steps requiring document confirmation: 1
Steps with related agency candidates: 10
Steps requiring agency confirmation: 1
Steps with confirmed duration: 0
Steps requiring duration confirmation: 11
Actual verified legal article mappings: 0
Server PDF generation: not implemented
Automatic legal original-text collection: not implemented
```

## Confirmation-Required Items

```text
IMPLEMENTER_DESIGNATION_REVIEW required documents: 서류 확인 필요
IMPLEMENTER_DESIGNATION_REVIEW related agencies: 기관 확인 필요
All core step durations: 기간 확인 필요
Most core step legal references: 근거 미연결
Article URLs: 링크 확인 필요 when no verified URL is present
```

## Next Data Improvements

```text
Official legal article mapping after MOLEG/API or reviewed legal dataset confirmation
Verified article titles and article URLs
Jurisdiction-specific ordinance mapping
Validated required document lists
Validated agency/responsible authority lists
Reviewed duration ranges or schedule guidance
Additional legal references per procedure step when confirmed
```

## Guardrails

Phase 17 does not invent law names, article numbers, agencies, documents, or criteria. Values remain TEST-only or confirmation-required unless already present in the current rules, seed, fixture, or backend result payload.
