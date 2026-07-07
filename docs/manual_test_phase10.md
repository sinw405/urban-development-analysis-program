# Phase 10 수동 테스트 체크리스트

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

기대 결과:

```text
TEST_LAW_DO_NOT_USE
TEST_ARTICLE_DO_NOT_USE
TEST_VERSION_DO_NOT_USE_CURRENT
TEST_VERSION_DO_NOT_USE_SCHEDULED
PROJECT_BASIC_REVIEW
TEST_PROJECT_DO_NOT_USE
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

## 4. 사업 분석 실행 확인

접속:

```text
http://localhost:5173/analyze
```

기본 TEST 입력값으로 분석 실행을 누릅니다.

기대 결과:

```text
분석 요약, 절차 목록, 단계별 법령 근거가 표시됩니다.
raw JSON은 "개발자용 원문 응답 보기" 접기 영역 안에서만 표시됩니다.
```

## 5. 분석 이력 목록 확인

접속:

```text
http://localhost:5173/analyses
```

기대 결과:

```text
저장된 분석 목록이 표시됩니다.
분석 ID, 사업명, 프로젝트 ID, 기준일, 생성일, 절차 수, 법령 근거 연결 수가 표시됩니다.
상세 보기 버튼을 누르면 /analyses/{analysisId} 화면으로 이동합니다.
저장된 이력이 없으면 "저장된 분석 이력이 없습니다."가 표시됩니다.
```

## 6. 분석 상세 확인

접속 예시:

```text
http://localhost:5173/analyses/1
```

기대 결과:

```text
저장된 result_payload가 사업 분석 화면과 같은 구조로 표시됩니다.
분석 요약, 절차 목록, 단계별 법령 근거가 표시됩니다.
없는 ID에 접근하면 한국어 오류 메시지가 표시됩니다.
raw JSON은 개발자용 접기 영역에서만 확인할 수 있습니다.
```

## 7. 대시보드 최근 분석 이력 확인

접속:

```text
http://localhost:5173
```

기대 결과:

```text
최근 분석 이력 섹션에 최근 분석 3~5건이 표시됩니다.
전체 분석 이력 보기 버튼이 /analyses로 이동합니다.
최근 이력 API 오류가 발생해도 대시보드의 다른 카드가 계속 표시됩니다.
```

## 8. TEST 데이터와 placeholder 확인

확인 항목:

```text
TEST legal reference는 개발 검증용 메타데이터로만 표시됩니다.
실제 법령명, 실제 조문번호, 실제 기준값이 화면에 임의로 표시되지 않습니다.
법제처 실제 네트워크 호출과 RAG는 사용하지 않습니다.
```
