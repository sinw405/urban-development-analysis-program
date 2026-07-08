# Release Notes v0.1 MVP

## Project

도시개발사업 관련 분석 프로그램

## Release Version

v0.1 MVP

## Release Purpose

v0.1 MVP는 도시개발사업 절차 분석 흐름을 로컬 환경에서 시연하고 검증하기 위한 버전입니다. 사업 정보를 입력하면 절차 로드맵, 법령 근거 연결 상태, 체크리스트, 분석 이력, 보고서형 요약을 확인할 수 있습니다.

## Current Features

```text
FastAPI backend health check and analysis API
PostgreSQL persistence for projects and analysis results
Alembic database migrations
YAML rule-based procedure engine
Procedure legal reference foundation
MOLEG ingest adapter foundation with network calls disabled by default
As-of law article version lookup foundation
Law update detection event foundation
React dashboard and analysis UI
Stored analysis history and detail UI
Procedure roadmap and step detail UI
Frontend-only checklist state
Report-style summary and browser print/PDF flow
TEST-only demo seed and manual QA flow
```

## Main Browser URLs

```text
http://localhost:5173/
http://localhost:5173/analyze
http://localhost:5173/analyses
http://localhost:5173/analyses/{analysisId}
http://localhost:5173/law-updates
```

## Main Technology Stack

```text
Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL
Frontend: React, TypeScript, Vite
Testing: pytest, TypeScript typecheck, Vite production build
Runtime/Local verification: Docker Compose, npm, Edge headless browser checks
Rules and placeholders: YAML rule files and TEST-only seed data
```

## Phase History Summary

```text
Phase 1: Basic API and analysis flow foundation
Phase 1.5: Persistence and migration foundation
Phase 2: YAML rule-based procedure engine
Phase 3: Legal reference data model foundation
Phase 4: MOLEG ingest adapter and service foundation
Phase 5: As-of law article version lookup foundation
Phase 6: As-of legal references in analysis results
Phase 7: Law update detection event foundation
Phase 8: React frontend MVP foundation
Phase 9: Local demo seed and browser test flow
Phase 9.5: Korean dashboard and UX cleanup
Phase 10: Analysis history list and detail UI
Phase 10.5: Browser UX stabilization
Phase 11: Procedure roadmap UI
Phase 12: Procedure checklist UI
Phase 13: Analysis report and browser print view
Phase 14: Analysis result data consistency
Phase 15: Final QA and release readiness
```

## Test Summary

Latest release-readiness verification used the existing backend, frontend, demo seed, browser, and print checks:

```text
backend pytest: 51 passed, 1 warning
demo seed: success
frontend typecheck: success
frontend build: success
browser routes checked: /, /analyze, /analyses, /analyses/{analysisId}, /analyses/999999, /law-updates
print/PDF checked: stored analysis detail and analysis screen through browser print-to-PDF
```

## Current Limitations

```text
Server-side PDF generation API is not implemented.
Real legal article datasets are not finalized.
Legal criteria, thresholds, and article mappings still require official source validation and expert review.
Local ordinance integration is not implemented.
Checklist state is frontend-only and is not saved per user.
Production deployment configuration is not finalized.
TEST_*_DO_NOT_USE data is for development verification only.
```

## Next Enhancement Candidates

```text
Actual Urban Development Act, enforcement decree, and enforcement rule article datasets
Advanced review and assessment decision rules
Local ordinance integration
Server-side PDF generation API
User-specific checklist state persistence
Deployment environment setup
```

## Legal Notice

본 분석 결과는 도시개발사업 절차 검토를 위한 참고자료입니다. 최종 적용 여부는 관계 법령 원문, 인허가권자 협의 및 전문가 검토를 통해 확인해야 합니다. 본 프로그램은 법적 유권해석, 법률 의견, 또는 최종 인허가 판단을 대체하지 않습니다.
