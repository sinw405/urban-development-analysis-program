# Phase 49 Legal Corpus Retrieval Foundation

## Existing infrastructure audit

| Capability | Status |
|---|---|
| PostgreSQL connection | EXISTING |
| Law/article DB search helpers | PARTIAL |
| PostgreSQL full-text search | MISSING |
| pg_trgm | MISSING |
| pgvector | MISSING |
| Elasticsearch | MISSING |
| Embedding provider/config | MISSING |
| Text normalization | PARTIAL, Phase 49 shared utility added |
| Structural article/table corpus | EXISTING |
| Citation-ready retrieval schema | MISSING, Phase 49 implemented |
| RAG/LLM generation | MISSING and out of scope |

## Architecture

`retrieve_legal_evidence(query, as_of, top_k, source_types)` builds a read-only corpus from verified production tables. Article documents use the existing `get_current_article_version` resolver. Attached-table documents select the newest effective version at or before `as_of` per `(law, table_key)`. Scheduled versions after the requested date are excluded.

The lexical baseline normalizes whitespace, case and punctuation without summarizing or rewriting legal text. It boosts matches in law names and titles over body matches, removes duplicate citation IDs, and uses deterministic citation ordering for ties.

## Retrieval document

Each result includes source type, law identifier/name, source identifier, article/table title, DB text and excerpt, effective date, version status, MST, provenance, citation ID, SHA-256 content hash and relevance score. No external URL is fabricated.

Articles remain article-sized. Attached tables remain table-sized because Phase 48 does not provide verified row boundaries. Arbitrary character chunking is not used.

## Index and vector readiness

No physical search table is added. Stable source identity plus SHA-256 content hash provides a vector-ready incremental reindex contract: a downstream indexer can upsert only new or changed hashes and retire source versions outside the selected as-of scope. PostgreSQL does not currently have pgvector or pg_trgm, and no embedding provider is configured. Vector/hybrid retrieval therefore remains PARTIAL for a later phase without introducing an external key.

## API

`POST /api/rag/retrieve` accepts query, as_of, top_k and optional source types (`article`, `attached_table`). Empty matches return an empty list. The response declares `deterministic_lexical_v1` and `vector_status=not_configured`.

## Safety

The corpus contains only Law/LawArticle/LawArticleVersion and LawAttachedTableEvidence rows. Internet content and generated legal interpretation are excluded. Current retrieval never searches multiple versions of one source for a single `as_of`, does not surface future scheduled versions early, and never manufactures missing evidence.
