# Final Feature Summary

## Overview

현재 프로그램은 도시개발사업 절차 분석 흐름을 로컬 환경에서 검증하기 위한 v0.1 MVP입니다. 화면과 데이터는 TEST/placeholder 정책을 유지하며, 실제 법령 조문번호나 기준값을 임의로 확정하지 않습니다.

## Dashboard

대시보드는 주요 기능으로 이동하는 시작 화면입니다. 사업 분석, 분석 이력, 법령 개정 감지 내역, 개발 검증 상태를 확인할 수 있습니다.

## New Analysis

`/analyze` 화면에서 TEST용 사업 정보를 입력하고 분석을 실행할 수 있습니다. 분석 결과는 백엔드 `/api/analyze` 응답을 기반으로 표시됩니다.

## Analysis Result Persistence

분석 요청 결과는 기존 백엔드 저장 흐름을 통해 `analysis_results.result_payload`에 저장됩니다. Phase 16에서는 이 저장 구조를 변경하지 않았습니다.

## Stored Analysis List

`/analyses` 화면에서 저장된 분석 이력을 확인할 수 있습니다. 분석 ID, 사업명 또는 프로젝트 정보, 기준일, 생성일, 절차 수, 법령 근거 연결 수를 확인하고 상세 화면으로 이동할 수 있습니다.

## Stored Analysis Detail

`/analyses/{analysisId}` 화면에서 저장된 분석 결과를 다시 열어볼 수 있습니다. 신규 분석 결과와 같은 표시 구조를 사용합니다.

## Procedure Roadmap

분석 결과의 절차를 로드맵 형태로 표시합니다. 각 단계는 단계명, 설명, 법령 근거 연결 여부, 필요 서류 수, 협의/인허가 기관 수, 예상 기간 상태를 보여줍니다.

## Procedure Step Detail

각 절차 단계의 상세 정보에는 법령 근거, 필요 서류, 협의/담당 기관, 예상 소요기간, 비고/주의사항, 데이터 출처 또는 연결 상태가 표시됩니다. 데이터가 없으면 확인 필요 상태로 표시합니다.

## Procedure Checklist

각 단계별로 실무 확인 항목을 체크할 수 있습니다. 체크 상태는 프론트엔드 화면 상태이며 서버에 저장하지 않습니다.

## Report Summary

분석 결과 하단에 보고서형 요약을 표시합니다. 사업 개요, 분석 기준, 절차 수, 법령 근거 연결 수, 확인 필요 항목, 단계별 요약, 참고용 고지 문구를 확인할 수 있습니다.

## Browser Print/PDF

보고서형 요약은 브라우저 인쇄 기능을 통해 출력하거나 PDF로 저장할 수 있습니다. 서버 PDF 생성 API는 아직 구현하지 않았습니다.

## Law Update Screen

`/law-updates` 화면에서 개발 검증용 TEST 법령 개정 이벤트와 영향받는 절차 코드를 확인할 수 있습니다.

## Developer Raw JSON

raw JSON은 개발자용 원문 응답 보기 영역에서만 확인할 수 있습니다. 일반 로드맵, 체크리스트, 보고서 영역에는 기본 노출하지 않습니다.

## Missing Data Display Policy

```text
법령 근거 없음: 근거 미연결
기관 없음: 기관 확인 필요
필요 서류 없음: 서류 확인 필요
기간 없음 또는 TODO 기간: 기간 확인 필요
상태 없음: 미확인
```
