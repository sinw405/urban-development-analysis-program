# Phase 11 수동 테스트 체크리스트

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

## 4. /analyze 로드맵 확인

```text
/analyze에서 기본 TEST 입력값으로 분석을 실행합니다.
분석 요약 아래에 "절차 로드맵" 섹션이 표시됩니다.
각 단계는 번호, 단계명, 설명, 단계 코드, 법령 근거 수, 예상 소요기간, 필요 서류, 협의기관을 표시합니다.
각 단계 상세에는 법령 근거, 필요 서류, 협의기관, 비고가 구조적으로 표시됩니다.
법령 근거가 없으면 "연결된 법령 근거가 없습니다."가 표시됩니다.
raw JSON은 "개발자용 원문 응답 보기" 접기 영역에서만 표시됩니다.
```

## 5. /analyses/:analysisId 저장 분석 상세 확인

```text
/analyses에서 상세 보기 버튼을 눌러 저장 분석 상세 화면으로 이동합니다.
저장된 result_payload도 /analyze와 같은 로드맵 UI로 표시됩니다.
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
실제 법령명, 실제 조문번호, 실제 기준값이 새로 표시되지 않습니다.
TEST_*_DO_NOT_USE 데이터는 개발 검증용으로만 표시됩니다.
MOLEG 실제 네트워크 호출과 RAG는 사용하지 않습니다.
```
