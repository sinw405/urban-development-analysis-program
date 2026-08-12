from datetime import date
from pathlib import Path

from app.core.config import Settings
from app.core.database import SessionLocal
from app.schemas.legal_generation import GroundedClaim, LegalAnswerResponse, LegalCitation
from app.schemas.legal_retrieval import LegalRetrievalResult
from app.services.legal_rag_evaluation_service import (
    LegalRagEvaluationCase, build_evaluation_report, compare_retrieval_modes,
    evaluate_generation, evaluate_retrieval, load_evaluation_cases, production_provider_readiness,
)
from app.services.embedding_provider import DeterministicTestEmbeddingProvider
from app.services.hybrid_legal_retrieval_service import retrieve_with_mode
from app.services.legal_retrieval_service import build_legal_corpus
from app.services.legal_vector_index_service import InMemoryLegalVectorIndex
from tests.test_phase49_legal_retrieval import KEY, _cleanup, _seed


def _case(**changes):
    values = dict(case_id='case', category='direct_article', question='seed question', as_of=date(2026, 1, 1),
                  source_types=['article'], retrieval_mode='lexical', top_k=5, expected_law_identifiers=['TEST_LAW'],
                  expected_source_types=['article'], expected_behavior='grounded')
    values.update(changes)
    return LegalRagEvaluationCase(**values)


def _evidence(source_type='article', effective=date(2025, 1, 1), text='current evidence', citation=None, source='source-current'):
    citation = citation or ('law:TEST_LAW:table:1:mst:200' if source_type == 'attached_table' else 'law:TEST_LAW:article:1:asof:2026-01-01')
    return LegalRetrievalResult(source_type=source_type, law_identifier='TEST_LAW', law_name='TEST_LAW_NAME',
        source_identifier=source, title='seed title', text=text, text_excerpt=text, effective_date=effective,
        version_status='current', mst='200', provenance={'source': 'TEST'}, citation_id=citation,
        content_hash='a' * 64, relevance_score=1.0)


def _answer(case, evidence, status='grounded'):
    citations = [LegalCitation(citation_id=item.citation_id, law_identifier=item.law_identifier, law_name=item.law_name,
        source_type=item.source_type, source_identifier=item.source_identifier, title=item.title,
        effective_date=item.effective_date, mst=item.mst, provenance=item.provenance, excerpt=item.text_excerpt,
        content_hash=item.content_hash) for item in evidence]
    claims = [GroundedClaim(text='seed grounded claim', citation_ids=[evidence[0].citation_id])] if status.startswith('grounded') and evidence else []
    return LegalAnswerResponse(status=status, answer='answer' if claims else None, claims=claims, citations=citations if claims else [],
        evidence=evidence, as_of=case.as_of, retrieval_mode=case.retrieval_mode, retrieval_status='available',
        generation_status='completed', provider_status='available', disclaimer='reference only')


def test_evaluation_fixture_parsing_and_all_required_categories():
    path = Path('tests/fixtures/phase53_legal_rag_evaluation.json')
    loaded = load_evaluation_cases(path)
    assert len(loaded) == 10
    categories = ['direct_article', 'procedure', 'attached_table', 'historical', 'current', 'future_leakage',
                  'insufficient', 'conflict', 'citation_attack', 'unrelated']
    cases = [_case(case_id=value, category=value, expected_behavior='insufficient_evidence',
                   expected_abstention=True, expected_law_identifiers=[], expected_source_types=[]) for value in categories]
    assert {item.category for item in cases} == set(categories)
    assert {item.category for item in loaded} == set(categories)


def test_retrieval_hit_rank_recall_mrr_and_metadata():
    result = evaluate_retrieval(_case(), [_evidence()])
    assert result.passed and result.expected_rank == 1
    assert result.recall_at_k == 1 and result.reciprocal_rank == 1
    assert result.citation_metadata_complete


def test_lexical_vector_hybrid_comparison_uses_rank_contracts():
    case = _case()
    comparison = compare_retrieval_modes(case, lambda mode: [_evidence()] if mode != 'vector' else [_evidence(source='vector')])
    assert set(comparison.results) == {'lexical', 'vector', 'hybrid'}
    assert all(item.passed and item.expected_rank == 1 for item in comparison.results.values())


def test_retrieval_detects_forbidden_source_and_future_content_leakage():
    case = _case(forbidden_source_identifiers=['future-source'], forbidden_content_contains=['scheduled future'])
    result = evaluate_retrieval(case, [_evidence(source='future-source', text='scheduled future')])
    assert not result.passed
    assert 'forbidden_source_leakage' in result.failure_reasons
    assert 'forbidden_content_leakage' in result.failure_reasons


def test_empty_result_correctness_for_unrelated_or_insufficient_case():
    case = _case(category='unrelated', expected_behavior='insufficient_evidence', expected_abstention=True,
                 expected_law_identifiers=[], expected_source_types=[])
    assert evaluate_retrieval(case, []).passed


def test_generation_grounding_and_citation_completeness_pass():
    case = _case()
    result = evaluate_generation(case, _answer(case, [_evidence()]))
    assert result.passed and result.citation_allow_list_valid
    assert result.citation_metadata_complete and result.disclaimer_present


def test_generation_detects_invalid_citation():
    case = _case()
    response = _answer(case, [_evidence()])
    response.claims[0].citation_ids = ['law:invented:article:999']
    result = evaluate_generation(case, response)
    assert not result.passed and 'citation_hallucination' in result.failure_reasons


def test_generation_detects_as_of_and_future_leakage():
    case = _case(category='future_leakage')
    response = _answer(case, [_evidence(effective=date(2027, 1, 1), text='scheduled future')])
    result = evaluate_generation(case, response)
    assert not result.passed and 'as_of_leakage' in result.failure_reasons


def test_attached_table_citation_and_provenance_are_preserved():
    case = _case(category='attached_table', source_types=['attached_table'], expected_source_types=['attached_table'],
                 attached_table_expected=True)
    evidence = [_evidence(source_type='attached_table')]
    retrieval = evaluate_retrieval(case, evidence)
    generation = evaluate_generation(case, _answer(case, evidence))
    assert retrieval.passed and retrieval.attached_table_hit
    assert generation.passed and generation.attached_table_preserved


def test_abstention_conflict_and_generation_unavailable_remain_distinct():
    insufficient = _case(case_id='none', category='insufficient', expected_behavior='insufficient_evidence',
                         expected_abstention=True, expected_law_identifiers=[], expected_source_types=[])
    assert evaluate_generation(insufficient, _answer(insufficient, [], 'insufficient_evidence')).passed
    conflict = _case(case_id='conflict', category='conflict', expected_behavior='conflicting_evidence')
    assert evaluate_generation(conflict, _answer(conflict, [_evidence()], 'grounded_with_conflicts')).passed
    unavailable = _case(case_id='unavailable', expected_behavior='generation_unavailable', expected_abstention=True)
    response = _answer(unavailable, [_evidence()], 'generation_unavailable')
    assert evaluate_generation(unavailable, response).passed and response.evidence


def test_repository_seeded_corpus_compares_modes_and_enforces_as_of():
    _cleanup(); _seed()
    try:
        with SessionLocal() as db:
            fixture = next(item for item in build_legal_corpus(db, date(2026, 1, 1), {'article'}) if item.law_identifier == KEY)
        question = fixture.text
        case = _case(question=question, expected_law_identifiers=[KEY])
        provider = DeterministicTestEmbeddingProvider()
        def runner(mode):
            index = InMemoryLegalVectorIndex()
            with SessionLocal() as db:
                return retrieve_with_mode(db, question, date(2026, 1, 1), 20, ['article'], mode,
                                          provider if mode != 'lexical' else None, index if mode != 'lexical' else None)[0]
        comparison = compare_retrieval_modes(case, runner)
        assert set(comparison.results) == {'lexical', 'vector', 'hybrid'}
        with SessionLocal() as db:
            old_corpus = build_legal_corpus(db, date(2024, 6, 1), {'article'})
            current_corpus = build_legal_corpus(db, date(2026, 1, 1), {'article'})
            old = [item for item in old_corpus if item.law_identifier == KEY]
            current = [item for item in current_corpus if item.law_identifier == KEY]
        assert all(item.effective_date <= date(2024, 6, 1) for item in old)
        assert all(item.effective_date <= date(2026, 1, 1) for item in current)
        assert old[0].mst == '100' and current[0].mst == '200'
    finally:
        _cleanup()


def test_report_aggregation_and_zero_failure_quality_gate():
    case = _case()
    retrieval = evaluate_retrieval(case, [_evidence()])
    generation = evaluate_generation(case, _answer(case, [_evidence()]))
    report = build_evaluation_report([case], [retrieval], [generation])
    assert report.total_cases == 1 and report.passed == 2 and report.failed == 0
    assert report.quality_gate_passed and report.blocker == []
    failed = evaluate_retrieval(case, [])
    failed_report = build_evaluation_report([case], [failed], [])
    assert not failed_report.quality_gate_passed and failed_report.blocker


def test_production_provider_readiness_is_boolean_only_and_test_provider_isolated(monkeypatch):
    for name in ('GENERATION_PROVIDER', 'GENERATION_API_KEY', 'GENERATION_MODEL'):
        monkeypatch.delenv(name, raising=False)
    readiness = production_provider_readiness(Settings())
    assert readiness.live_test_status == 'not_configured' and not readiness.api_key_present
    monkeypatch.setenv('GENERATION_PROVIDER', 'deterministic-test-only-v1')
    monkeypatch.setenv('GENERATION_API_KEY', 'phase53-secret-fixture')
    monkeypatch.setenv('GENERATION_MODEL', 'test-model')
    payload = production_provider_readiness(Settings()).model_dump_json()
    assert 'phase53-secret-fixture' not in payload
    assert not production_provider_readiness(Settings()).test_provider_isolated
