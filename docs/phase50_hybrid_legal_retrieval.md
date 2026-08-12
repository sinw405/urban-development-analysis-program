# Phase 50 Hybrid Legal Retrieval

## Capability

PostgreSQL 16.14 is available through `postgres:16-alpine`. The `vector` extension is neither installed nor listed in `pg_available_extensions`; pgvector persistence cannot be deployed safely in the current image. No failing extension migration was added.

## Architecture

Phase 49 lexical retrieval remains unchanged. `EmbeddingProvider` separates query/document embedding from retrieval. `DeterministicTestEmbeddingProvider` is explicit TEST_ONLY code and is never selected from settings. `UnavailableProductionEmbeddingProvider` provides the production adapter slot without requiring a secret.

`InMemoryLegalVectorIndex` is a vector-ready fallback implementation. It keys entries by provider and source identifier, compares content hashes, embeds only changed documents, retains unchanged documents and removes stale sources. It stores citation-ready retrieval documents rather than duplicated raw authenticated payloads.

Vector retrieval builds the same as-of corpus as lexical retrieval, so historical/current/scheduled filtering and attached-table handling remain identical. Results preserve citation ID, MST, effective date, provenance, excerpt and content hash.

## Hybrid fusion

Hybrid uses Reciprocal Rank Fusion with k=60. RRF was selected because lexical scores and cosine similarities have different scales; rank fusion is deterministic and avoids unsafe raw-score calibration. Citation ID deduplication occurs before Top-K output.

## API and fallback

`POST /api/rag/retrieve` adds `retrieval_mode=lexical|vector|hybrid`; the default remains lexical. Additive result metadata includes lexical/vector/fused score and rank. If production provider/index is unavailable, vector or hybrid mode returns lexical evidence with `fallback_used=true` and `vector_status=unavailable`, rather than failing the entire request.

## Production requirement

Production semantic retrieval remains blocked until the PostgreSQL image supports pgvector (for example a version-pinned pgvector image), the Python vector dependency is installed, and a production embedding adapter is configured with timeout, masking and failure policy. No external embedding or LLM API is called in Phase 50.

## T3.1

Lexical indexing is COMPLETE. Embedding provider, deterministic CI vector retrieval, hybrid fusion, content-hash incremental indexing contract, as-of safety and fallback are COMPLETE. Production vector persistence is unavailable due to the demonstrated infrastructure blocker; T3.1 is therefore PARTIAL for production deployment.
