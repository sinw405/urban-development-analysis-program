# Phase 19 Legal Reference Quality

## Goal

Phase 19 adds a legal reference quality management layer so users do not confuse TEST/demo candidate references with officially verified legal grounds.

## Quality Status Definitions

```text
candidate: 테스트, 초안, 후보 법령 근거입니다. 화면 검증과 연결 구조 확인을 위한 상태이며 공식 검증 완료 근거가 아닙니다.
verified: 공식 법령 원문 또는 전문가 검토를 통해 확인된 법령 근거입니다. Phase 19에서는 아직 사용하지 않습니다.
missing: 해당 절차 단계에 연결된 법령 근거가 아직 없습니다.
```

Korean UI labels:

```text
candidate -> 후보근거
verified -> 검증완료
missing -> 근거미확인
```

## Why Phase 18 Data Is Candidate

Phase 18 connected TEST demo seed legal references to the 11 core common procedure steps. These references use TEST-only law/article keys and placeholder mapping statuses. They prove that the data flow works from seed to API, roadmap, report, and browser print/PDF, but they are not official legal mappings.

Therefore, every Phase 18 core common procedure legal reference is displayed as `candidate` in Phase 19.

## API Representation

Phase 19 keeps existing response fields and adds supplemental quality fields:

```text
procedures[].legal_reference_status
procedures[].legal_references[].reference_quality
```

Existing legal reference fields such as `reference_status`, `placeholder`, `law_id`, `law_key`, `article_id`, `article_key`, `current_version`, and `versions` remain available.

## Promotion Criteria To Verified

A candidate reference can be promoted to verified only after all required checks are complete:

```text
Official legal source text confirmed
Article number/title confirmed
Effective date/version confirmed
Applicability to the procedure step reviewed
Permitting authority or expert review completed
Placeholder/TODO status removed
Source and verification evidence recorded
```

Phase 19 does not promote any reference to verified.

## MOLEG Or Official Source Integration Path

When MOLEG Open API or another official source is integrated later:

```text
1. Fetch and store official law/article/version data.
2. Match article data to procedure step codes.
3. Preserve candidate status until review is complete.
4. Promote to verified only after official source and expert review checks pass.
5. Keep missing for steps without a reviewed connection.
```

No external network calls or MOLEG Open API integration are added in Phase 19.

## Browser Print/PDF Verification Scope

Phase 19 updates the browser print/PDF report component so legal reference quality status and the candidate-reference notice are included in the printable report layout.

Actual PDF file saving remains a manual verification item in the user's browser print environment. Phase 19 does not add automated PDF generation, PDF file snapshot tests, download endpoints, or server-side PDF rendering.

## User-Facing Legal Notice

When candidate references are present, the UI/report/browser print-PDF path shows this notice:

```text
본 법령 근거는 현재 후보 데이터 기준으로 연결된 항목이며, 공식 법령 원문 및 인허가권자 확인이 필요합니다.
```

## Practical Use Caution

Candidate references are useful for workflow review and UI verification, but they must not be used as final legal grounds. Final applicability must be confirmed through official legal text, permitting authority consultation, and expert review.