# Phase 41 Live Law Change E2E

## Phase 41 목적

Phase 41의 목적은 법제처 공식 API에서 실제 서로 다른 도시개발법 MST 두 개를 확보하고, 해당 본문을 수집/정규화한 뒤 실제 조문 diff, 후보 preview, 명시적 검토, impact event, `needs_revalidation` 흐름을 end-to-end로 검증하는 것이다.

동일 MST 비교나 fixture 결과는 live 성공 결과로 보지 않는다.

## 법제처 버전 탐색 방식

프로젝트 기존 MOLEG client는 다음 endpoint를 사용한다.

- 검색: `/DRF/lawSearch.do`
- 본문: `/DRF/lawService.do`
- 기존 target: `law`
- 인증 파라미터: `OC`는 항상 redaction 대상

Phase 41에서는 먼저 `target=law`로 도시개발법 exact title 검색을 수행했고, 이어서 법령 연혁 목록 가능성이 있는 target 후보를 한 번에 하나씩 10초 이하 timeout으로 점검했다.

점검한 target:

| target | HTTP status | resultCode/resultMsg | item count | MST 목록 | 분류 |
|---|---:|---|---:|---|---|
| `law` | 200 | `00 / success` | 1 | `284059` | 정상, 현행 1건만 반환 |
| `eflaw` | 200 | 확인 불가 | 확인 불가 | 확인 불가 | 파싱 예외 |
| `oldlaw` | 200 | 없음 | 0 | 없음 | 빈 본문/파싱 실패 |
| `prelaw` | 200 | 없음 | 0 | 없음 | 빈 본문/파싱 실패 |
| `lsHst` | 200 | 없음 | 0 | 없음 | 빈 본문/파싱 실패 |
| `lsHistory` | 200 | 확인 불가 | 확인 불가 | 확인 불가 | 비어 있지는 않지만 기존 parser 기준 파싱 예외 |
| `lawHistory` | 200 | 없음 | 0 | 없음 | 빈 본문/파싱 실패 |

또한 `lawService.do`에 현재 MST `284059`와 과거 `efYd` 값을 조합해 요청했으나, 응답 메타데이터와 response hash가 모두 현재 버전과 동일했다. 따라서 현재 확인된 공식 API 호출만으로는 과거 본문 버전을 확보하지 못했다.

## 사용한 실제 law_id와 MST

공식 API 응답에서 확인된 도시개발법 현행 정보:

- 법령명: 도시개발법
- law_id: `002024`
- MST: `284059`
- 공포번호: `21447`
- 제개정구분: `타법개정`

## from/to 공포일 및 시행일

서로 다른 실제 MST 쌍은 아직 확보하지 못했다.

현재 공식 응답으로 확인된 단일 MST 정보:

| 구분 | MST | 공포일 | 시행일 |
|---|---|---|---|
| 현재 확인 버전 | `284059` | `2026-03-05` | `2026-07-01` |

## live 실행 명령

버전 탐색:

```bash
python -m scripts.moleg_live_change_e2e discover --law-name "도시개발법" --max-versions 6 --timeout-seconds 10
```

실제 서로 다른 MST가 발견된 경우 ingest/diff/impact dry-run:

```bash
python -m scripts.moleg_live_change_e2e run --law-name "도시개발법" --max-versions 6 --timeout-seconds 10 --apply-ingest
```

기존 DB에 두 MST가 저장된 경우 impact dry-run:

```bash
python -m scripts.moleg_change_impact analyze --law-name "도시개발법" --from-mst <이전_MST> --to-mst <현재_MST>
```

## diff 결과

현재까지 실제 서로 다른 MST 쌍을 확보하지 못했으므로 실제 live diff 결과는 생성하지 않았다.

기존 동일 MST 검증은 다음과 같지만 Phase 41 live 성공으로 간주하지 않는다.

- from MST: `284059`
- to MST: `284059`
- changed: `0`
- added: `0`
- removed: `0`
- unchanged: `109`

## candidate 결과

실제 서로 다른 MST diff가 없으므로 live change 기반 신규 candidate 결과는 없다.

현재 운영 후보 상태는 Phase 40 종료 상태와 동일하게 유지되어야 한다.

- live candidate: `19`
- confirmed: `0`
- unconfirmed: `19`
- rejected: `0`

## 확인되지 않은 후보 수

현재 실제 검토가 필요한 live 후보 수는 `19`건이다. Phase 41 live 탐색 과정에서 자동 confirm/reject를 수행하지 않았다.

## provenance 정책

실제 API 처리의 재현성에는 다음 메타데이터만 사용한다.

- `source_type`
- `law_id`
- `law_name`
- `from_mst`
- `to_mst`
- `requested_at`
- `received_at`
- `normalized_content_hash`
- `response_content_hash`
- `parser_version`
- `sanitized_endpoint_name`
- `result_code`
- `result_message`

전체 raw XML/HTML, 전체 payload, 인증 파라미터 값은 저장하지 않는다.

## secret redaction 정책

다음 값은 출력, 로그, DB, 문서, fixture에 저장하지 않는다.

- API 인증키
- `OC` 실제 값
- Authorization header
- cookie
- token류 값
- 전체 query string 중 인증값

문서와 CLI 출력에는 `secret_exposed=false` 또는 `[REDACTED]`만 사용한다.

## confirm/reject 원칙

- live 후보는 자동 confirm하지 않는다.
- confirm/reject는 반드시 명시적인 candidate ID 또는 event ID, reviewer, note가 필요하다.
- 일괄 자동 confirm 기능은 만들지 않는다.
- rejected 후보는 법령 개정으로 자동 부활하지 않는다.
- 명시적 검토 이력은 append-only audit event로 보존한다.

관리 CLI 예시:

```bash
python -m scripts.moleg_change_impact list-candidates --status unconfirmed
python -m scripts.moleg_change_impact preview --event-id <event_id>
python -m scripts.moleg_change_impact confirm --candidate-id <candidate_id> --reviewer <reviewer> --note <note>
python -m scripts.moleg_change_impact reject --candidate-id <candidate_id> --reviewer <reviewer> --note <note>
python -m scripts.moleg_change_impact audit-history --candidate-id <candidate_id>
```

## rollback 방법

impact dry-run은 DB를 변경하지 않는다.

```bash
python -m scripts.moleg_change_impact analyze --law-name "도시개발법" --from-mst <이전_MST> --to-mst <현재_MST>
```

rollback 검증은 test-only 옵션으로 수행한다.

```bash
python -m scripts.moleg_change_impact analyze --law-name "도시개발법" --from-mst <이전_MST> --to-mst <현재_MST> --force-rollback
```

live ingest rollback 검증은 test fixture에서 수행하며, 운영 후보 19건에는 적용하지 않는다.

## 알려진 한계

- 현재 확인된 공식 `target=law` 검색 응답은 도시개발법 현행 MST `284059` 1건만 반환했다.
- `lawService.do`에서 현재 MST에 과거 `efYd`를 넣어도 과거 본문이 반환되지 않았다.
- 점검한 historical target 후보에서 과거 MST 목록을 확보하지 못했다.
- 따라서 Phase 41 완료 기준인 “실제 서로 다른 MST 두 개 조회”와 “실제 changed/added/removed/unchanged diff 생성”은 아직 충족되지 않았다.
- fixture 테스트는 기능 회귀 확인용이며 live 성공 결과로 대체하지 않는다.

## 다음 Phase 권고사항

1. 법제처 공식 문서 또는 관리자 포털에서 법령 연혁 목록 API의 정확한 endpoint/target/parameter를 확인한다.
2. `lsHistory` 응답은 비어 있지 않았으므로 raw payload를 저장하지 않는 별도 sanitized parser probe를 만들어 root tag, resultCode 위치, item key만 확인한다.
3. 과거 MST 확보 후 `scripts.moleg_live_change_e2e run --apply-ingest`로 두 버전을 저장하고 DB-backed diff를 수행한다.
4. 실제 changed 후보가 확인되면 자동 confirm하지 말고 `preview` 결과를 사람이 검토하도록 한다.
5. 관리자 write UI는 다음 Phase에서 인증 구조와 함께 별도 설계한다.
