# Phase 46.5 - Assessment live legal grounding

## Evidence policy

All law names, external law identifiers, MST values, article numbers, titles, and effective versions in this phase came from MOLEG live responses or previously ingested MOLEG live data. No numeric applicability threshold was added. Legal-basis verification and applicability verification remain independent.

## Live and production result

MOLEG was configured. `eflaw` discovery returned HTTP 200 and resultCode 00. The Codex environment required `trust_env=false`; the default proxy-aware path failed. The existing version discovery and ingest pipeline selected the latest version effective on or before 2026-08-11 and persisted 515 article units across seven newly ingested laws. Urban Development Act data already existed from Phase 43 local acceptance.

| Assessment | Law / stable key | Verified article | MOLEG version source | Legal basis | Applicability | Threshold | Remaining issue |
|---|---|---|---|---|---|---|---|
| Urban planning committee review | Urban Development Act / `moleg:002024` | Article 8, Urban planning committee review, etc. | `MOLEG_LIVE:276975`, `MOLEG_LIVE:284059` | verified | unresolved | placeholder | Project-specific applicability and expert review |
| Environmental impact assessment | Environmental Impact Assessment Act / `moleg:002016` | Article 22, Subjects of environmental impact assessment | `MOLEG_LIVE:276833` | verified | unresolved | placeholder | Subordinate decree/table criteria not verified |
| Traffic impact assessment | Urban Traffic Improvement Promotion Act / `moleg:001754` | Article 15, Target areas and projects | `MOLEG_LIVE:284063` | verified | unresolved | placeholder | Subordinate criteria not verified |
| Disaster impact review | Countermeasures against Natural Disasters Act / `moleg:000959` | Article 4, Consultation on disaster impact assessment, etc. | `MOLEG_LIVE:276321` | verified | unresolved | placeholder | Detailed target conditions not verified |
| Landscape review | Landscape Act / `moleg:010447` | Article 27, Landscape review of development projects | `MOLEG_LIVE:276931` | verified | unresolved | placeholder | Ordinance/location-dependent criteria |
| Educational environment review | Educational Environment Protection Act / `moleg:012494` | Article 6, Approval of educational environment assessment report, etc. | `MOLEG_LIVE:280023` | verified | unresolved | placeholder | Detailed target conditions not verified |
| Underground safety assessment | Special Act on Underground Safety Management / `moleg:012468` | Article 14, Conducting underground safety assessment, etc. | `MOLEG_LIVE:271251` | verified | unresolved | placeholder | Excavation/decree criteria not verified |
| Buried cultural heritage review | Act on Protection and Investigation of Buried Cultural Heritage / `moleg:011152` | Article 7, Submission of surface survey report | `MOLEG_LIVE:285661` | verified | unresolved | placeholder | Project-specific survey requirement not verified |

Korean titles are stored exactly in `assessment_legal_reference_seeds.yaml`; this English table is descriptive only.

## Verification gate

A seed is accepted only when all of the following match in the production DB:

1. Stable MOLEG `law_key`.
2. Article number and exact article title.
3. Non-empty article-version text.
4. Expected `MOLEG_LIVE:<MST>` provenance.
5. Evidence term in the title or article text.
6. A version effective on or before the requested as-of date.

References use `reference_quality=verified` and `reference_scope=assessment`. Applicability and threshold provenance remain `unresolved` and `placeholder`; therefore no REQUIRED or NOT_REQUIRED result is emitted.

## Seed and idempotency

`apply_assessment_reference_seeds` supports dry-run and apply modes. It uses stable external keys rather than internal database primary keys. First production application created eight references in total; subsequent execution found eight existing references and created none. Each assessment has exactly one scoped reference.

## Appendix and subordinate-rule audit

The current normalized document model handles article units. The MOLEG payload exposes an appendix-edit flag, but the normalizer and database model do not persist appendix/table units as independently verifiable legal criteria. No new appendix parser was added. Numeric area, depth, scale, operator, or unit criteria remain placeholders until a dedicated subordinate-rule/table ingestion phase is defined.

## Local verification

```powershell
python -m scripts.phase46_5_assessment_live_verify --as-of 2026-08-11 --trust-env false
python -m scripts.phase46_5_assessment_live_verify --apply --as-of 2026-08-11 --trust-env false
```

The runner uses the existing client, discovery parameters, DB models, and seed service. It never prints credentials or authenticated URLs.
