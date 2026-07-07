# Phase 12 수동 테스트 체크리스트

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

브라우저 접속 URL:

```text
http://localhost:5173
```

## 4. /analyze 체크리스트 확인

```text
/analyze에서 기본 TEST 입력값으로 분석을 실행합니다.
절차 로드맵의 각 단계 상세에 "실무 확인 체크리스트"가 표시됩니다.
체크 항목은 법령 근거, 필요 서류, 협의기관, 예상 소요기간, 비고/주의사항 확인으로 표시됩니다.
체크박스를 선택하면 단계 상태가 미확인 -> 확인중 -> 확인완료로 바뀝니다.
확인완료 단계는 완료 상태 배지와 단계 카드 강조가 표시됩니다.
raw JSON은 개발자용 접기 영역에서만 표시됩니다.
```

## 5. /analyses/:analysisId 저장 분석 상세 확인

```text
/analyses에서 상세 보기 버튼을 눌러 저장 분석 상세 화면으로 이동합니다.
저장된 result_payload도 동일한 체크리스트 UI를 표시합니다.
이번 Phase에서는 체크 상태를 서버에 저장하지 않으므로 새로고침하면 초기 상태로 돌아가도 됩니다.
없는 ID 예시 /analyses/999999 접근 시 한국어 오류 메시지가 표시됩니다.
```

## 6. 기존 화면 영향 확인

```text
/analyses 분석 이력 목록이 정상 표시됩니다.
/ 대시보드 최근 분석 이력이 정상 표시됩니다.
/law-updates 법령 개정 감지 화면이 정상 표시됩니다.
Navigation active 스타일이 유지됩니다.
```

## 7. 정책 확인

```text
백엔드 API, DB migration, result_payload 저장 구조는 변경하지 않습니다.
실제 법령명, 실제 조문번호, 실제 기준값이 새로 표시되지 않습니다.
TEST_*_DO_NOT_USE 데이터는 개발 검증용으로만 표시됩니다.
MOLEG 실제 네트워크 호출과 RAG는 사용하지 않습니다.
```
