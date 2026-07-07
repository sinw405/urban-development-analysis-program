# Phase 9.5 수동 테스트 체크리스트

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

같은 명령을 다시 실행해도 중복 데이터가 생성되지 않아야 합니다.

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

## 4. 대시보드 확인

확인 항목:

```text
상단 프로젝트명이 "도시개발사업 절차 분석 프로그램"으로 보입니다.
메뉴가 "대시보드", "사업 분석", "법령 개정 감지"로 표시됩니다.
대시보드 카드에 사업 분석 시작, 법령 개정 감지 내역, 개발 검증 상태, 로컬 테스트 안내가 표시됩니다.
TEST 데이터 기반 MVP이며 실제 법령 조문과 기준값이 아직 연동되지 않았다는 안내가 표시됩니다.
```

## 5. 사업 분석 화면 확인

접속:

```text
http://localhost:5173/analyze
```

기본 입력값:

```text
사업명 = TEST_PROJECT_DO_NOT_USE
위치 = TEST_LOCATION_DO_NOT_USE
사업면적 = 100000
시행방식 = 혼용 방식
시행자 유형 = 민관 공동 SPC
관할 지자체 = TEST_LOCAL_GOVERNMENT_DO_NOT_USE
기준일 = 2099-06-15
```

기대 결과:

```text
분석 요약이 표시됩니다.
절차 목록이 표 형태로 표시됩니다.
PROJECT_BASIC_REVIEW 절차에 TEST 법령 근거 메타데이터가 표시됩니다.
법령 근거에는 법령 ID, 법령 키, 조문 ID, 조문 키, 조문 상태, 시행일, 출처가 표시됩니다.
raw JSON은 "개발자용 원문 응답 보기" 접기 영역 안에서만 표시됩니다.
```

## 6. 법령 개정 감지 화면 확인

접속:

```text
http://localhost:5173/law-updates
```

기대 결과:

```text
화면 제목이 "법령 개정 감지 내역"으로 표시됩니다.
TEST 법령 개정 이벤트가 표 형태로 표시됩니다.
영향받는 절차 코드에 PROJECT_BASIC_REVIEW가 표시됩니다.
감지 이벤트가 없으면 "감지된 법령 개정 이벤트가 없습니다."가 표시됩니다.
```

## 7. 한국어 UI 확인

확인 항목:

```text
화면 제목, 메뉴, 버튼, 입력 라벨, 도움말, 로딩 메시지, 오류 메시지가 한국어로 표시됩니다.
기술적인 오류 원문은 개발자용 상세 영역에만 표시됩니다.
API 내부 필드명이나 raw JSON 필드는 영어로 남아 있어도 됩니다.
```

## 8. 주의사항

```text
MOLEG 실제 네트워크 호출은 비활성화 상태입니다.
RAG는 아직 구현되지 않았습니다.
TEST_*_DO_NOT_USE 데이터는 화면 검증용이며 법적 판단 근거가 아닙니다.
```
