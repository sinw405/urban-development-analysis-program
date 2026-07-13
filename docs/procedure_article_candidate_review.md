# Procedure Article Candidate Review Report

Phase 39 read-only report. This file does not confirm or reject any candidate.
It does not store raw MOLEG XML/HTML or full article payloads. Reviewers should use the CLI detail view for normalized DB article text when needed.

- total candidates: 19
- confirmed candidates: 0
- rejected candidates: 0
- candidates needing review: 19

## Counts By Procedure

- PROJECT_BASIC_REVIEW: 5
- RELATED_AGENCY_CONSULTATION: 3
- RESIDENT_OPINION_HEARING: 6
- ZONE_DESIGNATION_REVIEW: 5

## Counts By Law

- 도시개발법: 11
- 도시개발법 시행령: 8

## Candidate Checklist

| ID | Status | Procedure | Law | MST | Effective Date | Article | Title | Match | Review note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 435 | unconfirmed | PROJECT_BASIC_REVIEW | 도시개발법 | 284059 | 2026-07-01 | 20 | 도시개발사업에 관한 공사의 감리 | title_keyword/90.0 | ?? ?? |
| 436 | unconfirmed | PROJECT_BASIC_REVIEW | 도시개발법 | 284059 | 2026-07-01 | 11 | 법인의 설립과 사업시행 등 | title_keyword/90.0 | ?? ?? |
| 437 | unconfirmed | PROJECT_BASIC_REVIEW | 도시개발법 | 284059 | 2026-07-01 | 12 | 도시개발사업시행의 위탁 등 | title_keyword/90.0 | ?? ?? |
| 438 | unconfirmed | PROJECT_BASIC_REVIEW | 도시개발법 | 284059 | 2026-07-01 | 21 | 도시개발사업의 시행 방식 | title_keyword/90.0 | ?? ?? |
| 439 | unconfirmed | PROJECT_BASIC_REVIEW | 도시개발법 | 284059 | 2026-07-01 | 21 | 순환개발방식의 개발사업 | title_keyword/90.0 | ?? ?? |
| 532 | unconfirmed | RELATED_AGENCY_CONSULTATION | 도시개발법 시행령 | 287279 | 2026-07-01 | 14 | 도시개발구역 지정 시 국토교통부장관과의 협의 | title_keyword/90.0 | ?? ?? |
| 533 | unconfirmed | RELATED_AGENCY_CONSULTATION | 도시개발법 시행령 | 287279 | 2026-07-01 | 41 | 협의기간 | title_keyword/90.0 | ?? ?? |
| 534 | unconfirmed | RELATED_AGENCY_CONSULTATION | 도시개발법 시행령 | 287279 | 2026-07-01 | 41 | 인허가 협의회의 운영 등 | title_keyword/90.0 | ?? ?? |
| 443 | unconfirmed | RESIDENT_OPINION_HEARING | 도시개발법 | 284059 | 2026-07-01 | 7 | 주민 등의 의견청취 | title_keyword/90.0 | ?? ?? |
| 444 | unconfirmed | RESIDENT_OPINION_HEARING | 도시개발법 | 284059 | 2026-07-01 | 51 | 공사 완료의 공고 | title_keyword/90.0 | ?? ?? |
| 445 | unconfirmed | RESIDENT_OPINION_HEARING | 도시개발법 | 284059 | 2026-07-01 | 53 | 조성토지등의 준공 전 사용 | text_keyword/60.0 | ?? ?? |
| 529 | unconfirmed | RESIDENT_OPINION_HEARING | 도시개발법 시행령 | 287279 | 2026-07-01 | 12 | 주민 등의 의견청취의 제외사항 | title_keyword/90.0 | ?? ?? |
| 530 | unconfirmed | RESIDENT_OPINION_HEARING | 도시개발법 시행령 | 287279 | 2026-07-01 | 11 | 주민의 의견청취 | title_keyword/90.0 | ?? ?? |
| 531 | unconfirmed | RESIDENT_OPINION_HEARING | 도시개발법 시행령 | 287279 | 2026-07-01 | 15 | 도시개발구역지정 및 개발계획수립의 고시 및 공람 등 | title_keyword/90.0 | ?? ?? |
| 440 | unconfirmed | ZONE_DESIGNATION_REVIEW | 도시개발법 | 284059 | 2026-07-01 | 4 | 개발계획의 수립 및 변경 | title_keyword/90.0 | ?? ?? |
| 441 | unconfirmed | ZONE_DESIGNATION_REVIEW | 도시개발법 | 284059 | 2026-07-01 | 5 | 개발계획의 내용 | title_keyword/90.0 | ?? ?? |
| 442 | unconfirmed | ZONE_DESIGNATION_REVIEW | 도시개발법 | 284059 | 2026-07-01 | 10 | 도시개발구역 지정의 해제 | title_keyword/90.0 | ?? ?? |
| 527 | unconfirmed | ZONE_DESIGNATION_REVIEW | 도시개발법 시행령 | 287279 | 2026-07-01 | 4 | 국토교통부장관의 도시개발구역 지정 | title_keyword/90.0 | ?? ?? |
| 528 | unconfirmed | ZONE_DESIGNATION_REVIEW | 도시개발법 시행령 | 287279 | 2026-07-01 | 6 | 개발계획의 단계적 수립 | title_keyword/90.0 | ?? ?? |

## Review Commands

```powershell
python -m scripts.procedure_article_review list --status unconfirmed
python -m scripts.procedure_article_review show --candidate-id <ID>
python -m scripts.procedure_article_review confirm --candidate-id <ID> --reviewer "<reviewer>" --note "<basis>"
python -m scripts.procedure_article_review reject --candidate-id <ID> --reviewer "<reviewer>" --note "<reason>"
python -m scripts.procedure_article_review reopen --candidate-id <ID> --reviewer "<reviewer>" --note "<reason>"
```

Actual legal confirmation requires human review. Do not approve candidates based only on keyword matches.
