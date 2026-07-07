# Phase 13 수동 테스트 체크리스트

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

## 4. /analyze 보고서형 요약 확인

```text
/analyze에서 기본 TEST 입력값으로 분석을 실행합니다.
분석 요약 아래에 "보고서형 요약" 섹션이 표시됩니다.
보고서에는 사업 개요, 분석 ID, 기준일, 생성일, 절차 단계 수, 법령 근거 연결 수, 절차 로드맵 요약, 단계별 상세 요약이 표시됩니다.
체크리스트 상태를 바꾸면 보고서의 체크리스트 진행 요약과 단계별 상태가 현재 화면 기준으로 반영됩니다.
raw JSON은 개발자용 접기 영역에서만 표시됩니다.
```

## 5. 인쇄하기 버튼 확인

```text
보고서형 요약 섹션의 "인쇄하기" 버튼을 누릅니다.
브라우저 인쇄 또는 PDF 저장 화면이 열리는지 확인합니다.
인쇄 미리보기에서 Navigation, 버튼, 입력 폼, 개발자용 raw JSON이 숨겨지는지 확인합니다.
```

## 6. /analyses/:analysisId 저장 분석 상세 확인

```text
/analyses에서 상세 보기 버튼을 눌러 저장 분석 상세 화면으로 이동합니다.
저장된 result_payload도 동일한 보고서형 요약을 표시합니다.
없는 ID 예시 /analyses/999999 접근 시 한국어 오류 메시지가 표시됩니다.
```

## 7. 기존 화면 영향 확인

```text
/analyses 분석 이력 목록이 정상 표시됩니다.
/ 대시보드 최근 분석 이력이 정상 표시됩니다.
/law-updates 법령 개정 감지 화면이 정상 표시됩니다.
Navigation active 스타일이 유지됩니다.
```

## 8. 정책 확인

```text
서버 PDF 생성, 파일 다운로드 API, 인증 기능은 구현하지 않습니다.
백엔드 API, DB migration, result_payload 저장 구조는 변경하지 않습니다.
실제 법령명, 실제 조문번호, 실제 기준값이 새로 표시되지 않습니다.
MOLEG 실제 네트워크 호출과 RAG는 사용하지 않습니다.
```
