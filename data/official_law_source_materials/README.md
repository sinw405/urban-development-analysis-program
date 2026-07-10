# 공식 법령 source material 보관 폴더

이 폴더에는 공식 출처에서 확인한 자료만 둡니다. 실제 seed 작성 전 검토자가 출처와 항목을 확인해야 하며, Codex가 기억이나 추정으로 조문번호, 기준값, 심의대상 요건을 작성하면 안 됩니다.

허용 자료 예시:
- 국가법령정보센터에서 직접 확인한 조문 목록
- 법제처 공식 페이지에서 수동 확인한 조문번호, 조문명, 시행일, anchor
- 내부 검토자가 공식 출처를 확인해 작성한 CSV 또는 YAML

금지 자료:
- 블로그, 카페, 비공식 요약
- 출처 불명 자료
- raw XML/JSON 전체 payload
- 조문본문 전문 전체 복사본
- serviceKey/token/key/OC 등 민감 query parameter가 포함된 URL

실제 seed 작성 전 필요한 최소 정보:
- law_key
- law_name
- article_no
- article_title
- article_anchor 또는 공식 URL
- sanitized_summary
- procedure_codes
- verified_by 또는 verification_note
- is_confirmed 여부