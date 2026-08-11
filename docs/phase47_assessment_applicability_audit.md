# Phase 47 Assessment Applicability Audit

## 범위와 원칙

기준일은 2026-08-11이다. Phase 46.5에서 검증한 8개 assessment의 법적 제도 근거와 `ProcedureLegalReference` 연결은 유지한다. 이번 Audit은 기존 `MolegLiveClient`로 현행 시행령 상세 XML을 조회하여 적용요건이 위치한 계층과 별표 존재를 확인했다. 법률 근거(legal basis), 적용범위(applicability), 숫자 기준(threshold)은 서로 독립된 상태로 관리한다.

법령명·조문·별표·숫자는 실제 MOLEG 응답에서 확인한 것만 기록했다. 별표 행을 정규화하지 못한 상태에서는 표 안의 문자열 존재만 provenance로 사용하며 자동 REQUIRED/NOT_REQUIRED 규칙으로 변환하지 않는다.

## Assessment applicability Audit

| Assessment | Verified legal basis | 적용 근거 계층 | 실제 확인 evidence | 상태 | 필요한 사업 입력 | 숫자 기준 | 예외/후속 검토 |
|---|---|---|---|---|---|---|---|
| 도시계획위원회 심의 | VERIFIED | 도시개발법 시행령 조문 | MST 287279, 시행 2026-07-01, 제5조 관련 절차 및 제14조 제외 구조 | REQUIRES_EXPERT_REVIEW | 심의 유형, 계획 변경 여부, 관할 지자체 기준 | PLACEHOLDER | 적용 시나리오·제외 및 위원회 운영기준 전문가 검토 |
| 환경영향평가 | VERIFIED | 환경영향평가법 시행령 별표 | MST 279237, 시행 2025-10-23, 별표 3에 도시개발법/도시개발사업 포함 | PARTIAL | 사업 세부 유형, 규모, 협의 시기, 예외 사실 | PLACEHOLDER | 별표 행·열 정규화 필요 |
| 교통영향평가 | VERIFIED | 도시교통정비 촉진법 시행령 별표 | MST 287283, 시행 2026-07-01, 별표 1에 도시개발법/도시개발사업 포함 | PARTIAL | 사업 세부 유형, 규모, 교통 조건, 지역 구분 | PLACEHOLDER | 범위·제외·제출시기 표 구조 정규화 필요 |
| 재해 영향 관련 검토 | VERIFIED | 자연재해대책법 시행령 별표 | MST 282993, 시행 2026-02-01, 별표 1에 도시개발사업 포함 | PARTIAL | 행정계획/개발사업 구분, 규모, 협의 단계 | PLACEHOLDER | 두 분기와 범위·협의시기 정규화 필요 |
| 경관 관련 심의 | VERIFIED | 경관법 시행령 제19조 및 별표 | MST 277919, 시행 2025-10-01, 별표 1에 도시개발사업 포함 | REQUIRES_EXPERT_REVIEW | 사업 유형, 규모, 위치, 지자체/조례 | PLACEHOLDER | 지역 조례·위원회 기준 미연동 |
| 교육환경 관련 평가/검토 | VERIFIED | 교육환경 보호에 관한 법률 시행령 조문 | MST 286641, 시행 2026-06-03, 제16조~제20조 평가 절차 확인 | UNRESOLVED | 위치, 교육환경보호구역 관계, 시설·입지 정보 | PLACEHOLDER | 도시개발사업 적용조건 직접 evidence 미확인 |
| 지하안전평가 | VERIFIED | 지하안전관리에 관한 특별법 시행령 제14조·별표 1 | MST 283007, 시행 2026-02-01, 별표 1에 도시개발 문자열 포함 | PARTIAL | 굴착깊이, 공사·사업 유형, 별표상 세부 범위 | PLACEHOLDER | 제23조의 10m 이상 20m 미만은 소규모 평가 문언이므로 일반 지하안전평가 threshold로 승격하지 않음 |
| 매장유산 조사/검토 | VERIFIED | 매장유산 보호 및 조사에 관한 법률 시행령 조문 | MST 285999, 시행 2026-05-17, 제5조의2~제5조의4 및 제10조 조사·공사 관련 구조 확인 | UNRESOLVED | 위치, 면적, 지표조사·보존구역·공사 유형 | PLACEHOLDER | 도시개발사업 적용범위·제외·행정해석 추가 확인 |

결론: VERIFIED applicability 0건, PARTIAL 4건, UNRESOLVED 2건, REQUIRES_EXPERT_REVIEW 2건이다. VERIFIED numeric threshold는 0건이며 8건 모두 `TODO_PLACEHOLDER_DO_NOT_USE_AS_CRITERIA`를 유지한다.

## 별표/부속표 capability Audit

- A. MOLEG 법령 상세 XML은 `법령 -> 별표 -> 별표단위`로 별표 metadata와 `별표내용`을 제공한다.
- B. 확인한 응답에는 별표번호, 별표제목, 별표내용과 관련 link metadata가 존재한다.
- C. 현재 `MinimalMolegPayloadParser`와 `Law/LawArticle/LawArticleVersion` ingest는 `조문단위`만 정규화하며 별표를 저장하지 않는다.
- D. applicability 자동화를 위해서는 별표 원문 blob 저장만으로 부족하고, 행/열·병합셀·각주·예외·적용시기 provenance를 보존하는 별도 구조가 필요하다.
- E. 이번 Phase에서는 거대한 범용 parser를 만들지 않았다. 공식 응답의 법령/MST/시행일/조문/별표번호·제목을 외부 evidence config에 기록하는 최소 지원만 추가했다.

따라서 현재 API 응답의 `applicability_evidence`는 검증 추적용이며 실행 가능한 threshold rule이 아니다.

## 구현 및 안전 gate

`rules/assessment_applicability_evidence.yaml`을 별도 로드한다. 기존 `assessment_rules.yaml`의 business criteria와 Phase 46.5 legal reference seed는 변경하지 않았다. 응답에는 `applicability_evidence`가 additive로 추가된다.

검증기는 다음을 강제한다.

- assessment code 중복 금지
- evidence status 허용값 제한
- law name, MST, hierarchy, source, supports 필수
- threshold가 `verified`이면 value/unit/operator/law/source locator/effective date 모두 필수
- partial/unresolved/expert evidence는 `verified_outcome`을 만들지 않음
- required input이 없으면 기존처럼 NEED_MORE_INFO
- 입력이 있어도 legal basis/applicability/threshold gate가 모두 verified가 아니면 UNRESOLVED

`requires_expert_review`는 별도 신호로 유지하되 기존 `determination_status` contract를 깨지 않는다.

## as-of 및 provenance

법적 제도 근거의 as-of 선택은 기존 `ProcedureLegalReference -> Law -> LawArticle -> LawArticleVersion` 경로를 그대로 사용한다. Applicability evidence에는 Live 조회에서 선택한 MST와 effective date를 보존한다. 별표가 DB에 정규화되지 않아 applicability evidence 자체는 아직 `LawArticleVersion` as-of resolver의 대상이 아니며, 이것이 VERIFIED 승격 blocker다.

## S2 Acceptance Audit

| 항목 | 상태 | 근거/남은 일 |
|---|---|---|
| T2.1 표준 절차 그래프 | COMPLETE | Phase 45 표준·세부 graph 및 dependency 유지 |
| T2.2 시행방식 분기 | COMPLETE | 수용/환지/혼용 regression 유지 |
| T2.3 시행자 유형 분기 | COMPLETE | 공공/민간/민관SPC regression 유지 |
| T2.4 심의·평가 판별 | PARTIAL | legal basis 8/8 verified, applicability 0/8 verified; 안전 미판정은 동작 |
| T2.5 규칙 외부화/로더 | COMPLETE | assessment rules, legal seeds, applicability evidence 모두 외부 YAML 및 validation |
| T2.6 analyze service | COMPLETE | 기존 POST /api/analyze에 additive evidence, backward compatibility 유지 |
| T2.7 규칙 테스트/버전관리 | COMPLETE | serialized matrix, Phase 46/46.5/47 validation 및 regression 존재 |

S2 완료의 핵심 blocker는 T2.4이다. 시행령 별표를 as-of 가능한 normalized entity/row evidence로 수집하고, 필요한 경우 자치법규·고시 소스를 연동한 뒤 전문가가 applicability/threshold를 승인해야 한다.

## 보안

Evidence config에는 API key, OC query, 전체 인증 URL, raw exception, raw MOLEG payload를 저장하지 않는다. source는 `MOLEG_LIVE_PHASE47` 식별자만 보존한다.

## 후속 권고

다음 작업은 범용 RAG나 UI가 아니라, 우선순위를 정한 assessment에 대해 별표 원문 보존 + 최소 구조화 + 전문가 승인 workflow를 설계하는 것이다. 자치법규 의존 항목은 별도 연동 없이는 전국 공통 자동판정으로 승격하지 않는다.
