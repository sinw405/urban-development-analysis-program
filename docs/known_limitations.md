# Known Limitations

## Server PDF Generation

서버에서 PDF 파일을 생성하거나 다운로드하는 API는 아직 구현하지 않았습니다. 현재는 브라우저 인쇄 또는 브라우저 PDF 저장 기능을 사용합니다.

## Real Legal Dataset

실제 도시개발 관련 법령 조문 데이터셋은 아직 확정하지 않았습니다. 법령명, 조문번호, 기준값은 공식 출처 확인과 전문가 검토가 필요합니다.

## Review and Assessment Rules

심의, 평가, 영향 검토 대상 여부를 확정하는 규칙은 아직 고도화가 필요합니다. placeholder와 TODO 기준값은 실제 판단 기준으로 사용하면 안 됩니다.

## Local Ordinance Integration

지자체 조례 연동은 아직 구현하지 않았습니다. 지역별 조례나 고시, 지침은 후속 단계에서 별도 검토가 필요합니다.

## Checklist Persistence

절차별 체크리스트 상태는 현재 프론트엔드 화면 상태입니다. 사용자별 서버 저장, 계정별 이력 관리, 새로고침 후 복원 기능은 아직 구현하지 않았습니다.

## Deployment Environment

운영 배포 환경, 보안 설정, 배포 자동화, 운영 모니터링은 아직 구성하지 않았습니다.

## Legal Interpretation

본 프로그램은 법적 유권해석이나 최종 인허가 판단을 제공하지 않습니다. 결과는 참고자료이며 관계 법령 원문, 인허가권자 협의, 전문가 검토가 필요합니다.

## Test Data Separation

`TEST_*_DO_NOT_USE` 데이터는 개발 검증용입니다. 실제 사업 데이터, 실제 법령 데이터, 실제 기관/서류 데이터처럼 사용하면 안 됩니다.
