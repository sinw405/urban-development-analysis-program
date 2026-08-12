# Phase 53 Legal RAG Evaluation

Phase 53 evaluates the existing Phase 49-52 retrieval and grounded-generation contracts. It does not change POST /api/rag/retrieve or POST /api/rag/answer.

## Deterministic evaluation

Run: .\\.venv\\Scripts\\python.exe -m pytest -q tests/test_phase53_legal_rag_evaluation.py

Fixtures use only repository-seeded article, version, and attached-table evidence. Metrics cover hit at K, rank, recall at K, reciprocal rank, citation completeness, forbidden leakage, attached-table preservation, abstention, and grounding. Raw lexical and cosine scores are never compared.

The quality gate requires zero citation hallucination, as-of or forbidden-source leakage, no-evidence answers, attached-table provenance loss, and regression failures. This validates grounding contracts, not subjective prose quality.

## Production and live evaluation

Readiness reports only non-secret booleans. API keys, authorization headers, and environment values are excluded. Normal pytest never makes a live request. A live smoke test requires separately reviewed explicit opt-in and may incur provider cost. Without opt-in, report LIVE QUALITY TEST PENDING.

Before production enablement, verify model availability, JSON response support, timeout behavior, deployment-secret injection, Korean legal prompts, latency, cost, and semantic quality against current official source text.
