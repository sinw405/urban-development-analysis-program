# Phase 14 수동 테스트 체크리스트

이 문서는 개발 검증용 TEST_*_DO_NOT_USE 데이터만 사용합니다. 실제 법령명, 실제 조문번호, 실제 기준값을 입력하거나 확인하지 않습니다.

## 1. 백엔드 실행

```powershell
cd C:\Users\poiu2\Desktop\도시개발사업_관련_분석_프로그램
docker compose up --build --detach
docker compose exec backend alembic upgrade head
```

## 2. demo seed 실행

```powershell
docker compose exec backend python -m app.dev_seed
```

## 3. 프론트엔드 실행

```powershell
cd C:\Users\poiu2\Desktop\도시개발사업_관련_분석_프로그램\frontend
npm install
npm run dev
```

## 4. /analyze 신규 분석 결과 확인

```text
/analyze에서 기본 TEST 입력값으로 분석을 실행합니다.
분석 요약에 전체 절차 수, 법령 근거 연결 수, 근거 미연결 수, 서류/기관 확인 필요 단계 수가 표시됩니다.
절차 로드맵의 각 단계가 근거 미연결, 서류 확인 필요, 기관 확인 필요, 기간 확인 필요를 빈칸 없이 표시합니다.
raw JSON은 개발자용 접기 영역에서만 표시됩니다.
```

## 5. /analyses 및 /analyses/:analysisId 확인

```text
/analyses 분석 이력 목록이 정상 표시됩니다.
상세 보기로 /analyses/:analysisId에 들어가도 동일한 정규화 표시 정책이 적용됩니다.
/analyses/999999 접근 시 한국어 오류 메시지가 표시됩니다.
```

## 6. /law-updates 영향 확인

```text
/law-updates 법령 개정 감지 화면이 기존처럼 표시됩니다.
PROJECT_BASIC_REVIEW impacted step 표시가 유지됩니다.
```

## 7. 보고서와 인쇄 확인

```text
보고서형 요약에 전체 절차 수, 근거 법령 연결 수, 근거 미연결 수, 서류/기관/기간 확인 필요 수가 표시됩니다.
단계별 요약 테이블이 표시됩니다.
참고 고지 문구가 표시됩니다.
인쇄 미리보기 또는 PDF 출력에서 Navigation, 버튼, raw JSON이 숨겨지는지 확인합니다.
```

## 8. 데이터 누락 표시 정책 확인

```text
법령 근거 없음은 "근거 미연결"으로 표시됩니다.
기관 없음은 "기관 확인 필요"로 표시됩니다.
서류 없음은 "서류 확인 필요"로 표시됩니다.
기간 없음 또는 TODO 기간은 "기간 확인 필요"로 표시됩니다.
상태 없음은 "미확인"으로 표시됩니다.
```

## 9. 정책 확인

```text
임의 법령명, 조문번호, 기관명, 서류명은 생성하지 않습니다.
백엔드 API, DB migration, result_payload 저장 구조는 변경하지 않습니다.
MOLEG 실제 네트워크 호출과 RAG는 사용하지 않습니다.
```
