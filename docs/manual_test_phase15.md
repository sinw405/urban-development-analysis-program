# Phase 15 수동 QA 체크리스트

## 목표

Phase 15는 현재 로컬 MVP의 릴리즈 준비 상태를 점검합니다. 라우트 안정성, 한국어 문구, 데이터 누락 표시, 인쇄/PDF 출력, 문서 재현성을 확인합니다. 백엔드 API, DB migration, 서버 PDF 생성, 실제 법령 데이터셋, RAG는 추가하지 않습니다.

## 실행 준비

```powershell
docker compose up --build --detach
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.dev_seed
docker compose exec backend pytest

cd frontend
npm install
npm run typecheck
npm run build
npm run dev
```

## 점검 라우트

```text
/
/analyze
/analyses
/analyses/{existingAnalysisId}
/analyses/999999
/law-updates
```

## 신규 분석 테스트

1. `/analyze` 화면을 엽니다.
2. `TEST_PROJECT_DO_NOT_USE` 같은 TEST 전용 입력값으로 분석을 실행합니다.
3. 분석 요약, 절차 로드맵, 체크리스트, 보고서형 요약, 개발자용 원문 영역이 표시되는지 확인합니다.
4. 일반 로드맵/보고서 영역에 raw JSON이 노출되지 않는지 확인합니다.

기대 결과: 분석이 정상 완료되고 사용자 노출 문구가 자연스러운 한국어로 표시됩니다.

## 저장 분석 상세 테스트

1. `/analyses` 화면을 엽니다.
2. 저장된 분석을 선택합니다.
3. `/analyses/{existingAnalysisId}` 화면에서 신규 분석 결과와 동일한 AnalysisResult 구조가 표시되는지 확인합니다.
4. 보고서형 요약과 인쇄 버튼이 표시되는지 확인합니다.

기대 결과: 저장된 `result_payload`가 기존 백엔드 응답 구조와 저장 방식을 변경하지 않고 표시됩니다.

## 없는 분석 ID 테스트

1. `/analyses/999999` 화면을 엽니다.
2. 한국어 오류 또는 찾을 수 없음 메시지가 표시되는지 확인합니다.
3. 앱 전체 레이아웃과 Navigation이 깨지지 않는지 확인합니다.

기대 결과: 화면이 중단되지 않고 사용자가 다른 메뉴로 이동할 수 있습니다.

## 법령 개정 감지 화면 영향 확인

1. `/law-updates` 화면을 엽니다.
2. TEST law update event가 기존처럼 표시되는지 확인합니다.
3. 영향받는 절차 코드가 있을 때 정상 표시되는지 확인합니다.

기대 결과: Phase 14/15 문서 및 QA 정리로 인한 화면 회귀가 없습니다.

## 인쇄/PDF 확인

1. `/analyses/{existingAnalysisId}` 화면을 엽니다.
2. 보고서 인쇄 버튼 또는 브라우저 인쇄 기능을 사용합니다.
3. 인쇄 출력에서 Navigation, 버튼, 입력 폼, 개발자 raw JSON 영역이 숨겨지는지 확인합니다.
4. 보고서형 요약과 참고용 고지 문구가 인쇄 화면에 표시되는지 확인합니다.

선택 확인: `/analyze`에서 신규 분석을 실행한 뒤 같은 방식으로 인쇄/PDF 출력을 확인합니다.

## raw JSON 노출 위치

raw JSON은 개발자용 원문 응답 보기 영역에만 표시되어야 합니다. 일반 절차 로드맵, 체크리스트, 보고서형 요약에는 raw JSON을 노출하지 않습니다.

## 데이터 누락 표시 정책

빈 값이나 불확실한 값은 다음처럼 명확한 한국어 상태로 표시합니다.

```text
법령 근거 없음: 근거 미연결
기관 없음: 기관 확인 필요
필요 서류 없음: 서류 확인 필요
기간 없음 또는 TODO 기간: 기간 확인 필요
상태 없음: 미확인
```

## 기존 API/DB 호환성

Phase 15에서 변경하지 않는 항목:

```text
백엔드 API 응답 구조
DB schema
Alembic migration
analysis_results.result_payload 저장 방식
법제처 네트워크 호출 방식
```

## DB migration

Phase 15에서는 신규 DB migration을 추가하지 않습니다.

## 남은 한계사항

```text
서버 PDF 생성 API는 아직 구현하지 않았습니다.
실제 법령 조문 데이터셋은 아직 확정하지 않았습니다.
법령 기준값과 조문 매핑은 공식 출처 검증이 필요합니다.
체크리스트 상태는 후속 저장 기능 전까지 프론트엔드 화면 상태입니다.
본 프로그램은 참고자료이며 법적 유권해석 또는 최종 인허가 판단을 대체하지 않습니다.
```
