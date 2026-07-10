# Official Seed Batch 1 Authoring Policy

Batch 1의 목적은 전체 법령을 복사하는 것이 아니라, 절차 분석에 필요한 핵심 조문 후보를 공식 출처 확인 후 seed로 관리하는 것입니다.

원칙:
- 실제 조문번호, 기준값, 심의대상 요건은 추정하지 않습니다.
- 공식 출처 파일, 사용자가 제공한 공식 조문 목록, 또는 검토 완료 source material이 있을 때만 seed를 작성합니다.
- Batch 1에는 모든 조문을 넣지 않고, 절차 분석과 직접 연결되는 핵심 후보만 넣습니다.
- seed에는 sanitized_summary, article_title, article_anchor/reference, source metadata만 저장합니다.

공식 출처 확인 기준:
- 국가법령정보센터 또는 법제처 공식 페이지에서 조문번호와 조문명을 확인합니다.
- official_source_url에는 serviceKey, token, key, OC 등 민감 query parameter를 포함하지 않습니다.
- 검토자는 source_checked_at_optional, verified_by_optional, verification_note 중 필요한 항목을 기록합니다.

is_confirmed 기준:
- true: 공식 출처와 procedure_code 연결 사유가 검토자 기록으로 남아 있고, 조문 후보가 해당 절차의 근거로 사용할 수 있음이 확인된 경우.
- false: 공식 출처는 확인했지만 절차 연결성 또는 적용 범위에 추가 검토가 필요한 경우.

sanitized_summary 작성 방법:
- 조문본문 전문을 붙여넣지 않습니다.
- 절차 분석에 필요한 범위의 짧은 요약과 anchor/reference만 남깁니다.
- 기준값이나 요건은 공식 출처에서 확인된 경우에만 요약합니다.

금지 필드:
- raw_payload
- raw_json
- raw_xml
- full_text
- article_full_text
- original_body
- body
- content_raw

검증 및 import 절차:
1. `python -m scripts.validate_official_seed_intake`
2. `python -m scripts.generate_official_seed_from_intake --dry-run`
3. 검토자 signoff 후 `python -m scripts.generate_official_seed_from_intake --apply`
4. `python -m scripts.validate_official_law_seeds`
5. `python -m scripts.import_official_law_seeds --dry-run`
6. 필요 시 `python -m scripts.import_official_law_seeds`

import 후 확인:
- `GET /api/legal-references/official-law-seeds/status`
- `GET /api/legal-references/official-law-snapshot`
- `/api/analyze` 응답에서 `official_seed_db` 후보 우선순위와 confirmed 여부를 확인합니다.

검토자 signoff가 필요한 이유:
- 법령 조문번호와 절차 연결은 업무 판단에 영향을 주므로 자동 생성이나 추정으로 확정할 수 없습니다.
- Batch 1은 수동 official seed의 품질 기준을 만드는 단계입니다.