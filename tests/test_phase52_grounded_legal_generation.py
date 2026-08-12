from datetime import date
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import SessionLocal
from app.main import app
from app.schemas.legal_generation import GenerationDraft, GroundedClaim
from app.services.generation_provider import (
    DeterministicTestGenerationProvider,
    GenerationProviderUnavailable,
    OpenAICompatibleGenerationProvider,
    production_generation_provider,
)
from app.services.grounded_legal_generation_service import answer_legal_question, build_generation_prompt
from tests.test_phase49_legal_retrieval import KEY, _cleanup, _seed


client = TestClient(app)


class InvalidCitationProvider:
    provider_id = 'invalid-test-only'
    model_id = 'invalid-test-only-v1'

    def generate(self, system_prompt, user_prompt):
        return GenerationDraft(
            status='grounded',
            claims=[GroundedClaim(text='근거가 있다고 주장합니다.', citation_ids=['law:invented:article:999'])],
        )


class UnavailableProvider:
    provider_id = 'unavailable-test-only'
    model_id = 'unavailable-test-only-v1'

    def generate(self, system_prompt, user_prompt):
        raise GenerationProviderUnavailable('hidden provider detail')


class ConflictProvider:
    provider_id = 'conflict-test-only'
    model_id = 'conflict-test-only-v1'

    def generate(self, system_prompt, user_prompt):
        import json
        citation_id = json.loads(user_prompt)['evidence'][0]['citation_id']
        return GenerationDraft(
            status='conflicting_evidence',
            claims=[GroundedClaim(text='근거별 조건이 달라 추가 검토가 필요합니다.', citation_ids=[citation_id])],
            warnings=['근거 간 적용 조건이 다릅니다.'],
        )


class MustNotRunProvider:
    provider_id = 'must-not-run-test-only'
    model_id = 'must-not-run-test-only-v1'

    def generate(self, system_prompt, user_prompt):
        raise AssertionError('No-evidence requests must not invoke generation.')


def _answer(question, as_of, provider, source_types=None):
    with SessionLocal() as db:
        return answer_legal_question(
            db=db, question=question, as_of=as_of, top_k=20, source_types=source_types,
            retrieval_mode='lexical', generation_provider=provider, settings=Settings(),
        )


def test_grounded_claims_use_only_retrieved_citations_and_current_as_of():
    _cleanup(); _seed()
    try:
        response = _answer('도시개발구역 지정 개발계획', date(2026, 1, 1), DeterministicTestGenerationProvider(), ['article'])
        allowed = {item.citation_id for item in response.evidence}
        assert response.status == 'grounded' and response.claims
        assert set(response.claims[0].citation_ids) <= allowed
        assert response.citations[0].citation_id in response.answer
        assert all(item.mst == '200' for item in response.evidence if item.law_identifier == KEY)
        assert all('미래 예정' not in item.text for item in response.evidence)
    finally:
        _cleanup()


def test_hallucinated_citation_is_blocked_without_repairing_it():
    _cleanup(); _seed()
    try:
        response = _answer('도시개발구역 지정', date(2026, 1, 1), InvalidCitationProvider(), ['article'])
        assert response.status == 'validation_failed'
        assert response.answer is None and response.citations == []
        assert response.evidence and 'invented' not in response.model_dump_json()
    finally:
        _cleanup()


def test_no_evidence_abstains_without_invoking_generation(monkeypatch):
    monkeypatch.setattr(
        'app.services.grounded_legal_generation_service.retrieve_with_mode',
        lambda *args, **kwargs: ([], 'not_configured', False),
    )
    response = _answer('절대로 존재하지 않는 검색어 phase52', date(2026, 1, 1), MustNotRunProvider())
    assert response.status == 'insufficient_evidence'
    assert response.generation_status == 'not_invoked'
    assert response.evidence == [] and '확정하기 어렵습니다' in response.answer


def test_attached_table_grounding_keeps_table_identity_and_provenance():
    _cleanup(); _seed()
    try:
        response = _answer('환경영향평가 대상', date(2026, 1, 1), DeterministicTestGenerationProvider(), ['attached_table'])
        assert response.status == 'grounded'
        assert response.citations[0].source_type == 'attached_table'
        assert ':table:' in response.citations[0].citation_id
        fixture = next(item for item in response.evidence if item.law_identifier == KEY)
        assert fixture.mst == '200'
        assert fixture.provenance['secret_exposed'] is False
    finally:
        _cleanup()


def test_generation_failure_preserves_retrieval_evidence():
    _cleanup(); _seed()
    try:
        response = _answer('개발계획', date(2026, 1, 1), UnavailableProvider())
        assert response.status == 'generation_unavailable' and response.answer is None
        assert response.evidence and response.generation_status == 'unavailable'
        assert 'hidden provider detail' not in response.model_dump_json()
    finally:
        _cleanup()


def test_conflicting_evidence_is_visible_in_status_and_warnings():
    _cleanup(); _seed()
    try:
        response = _answer('개발계획', date(2026, 1, 1), ConflictProvider())
        assert response.status == 'grounded_with_conflicts'
        assert response.warnings == ['근거 간 적용 조건이 다릅니다.']
        assert response.citations
    finally:
        _cleanup()


def test_prompt_contains_complete_evidence_contract_without_full_source_text():
    _cleanup(); _seed()
    try:
        response = _answer('환경영향평가 대상', date(2026, 1, 1), DeterministicTestGenerationProvider(), ['attached_table'])
        prompt = build_generation_prompt('질문', date(2026, 1, 1), response.evidence)
        for field in ('citation_id', 'law_identifier', 'law_name', 'source_type', 'source_identifier', 'title', 'effective_date', 'mst', 'provenance', 'excerpt', 'content_hash'):
            assert field in prompt
        assert 'GENERATION_API_KEY' not in prompt
    finally:
        _cleanup()


def test_test_only_provider_is_never_selected_by_production_settings(monkeypatch):
    for name in ('GENERATION_PROVIDER', 'GENERATION_API_KEY', 'GENERATION_MODEL'):
        monkeypatch.delenv(name, raising=False)
    assert production_generation_provider(Settings()) is None
    monkeypatch.setenv('GENERATION_PROVIDER', 'deterministic-test-only-v1')
    monkeypatch.setenv('GENERATION_API_KEY', 'top-secret')
    monkeypatch.setenv('GENERATION_MODEL', 'model')
    assert production_generation_provider(Settings()) is None


def test_production_provider_parses_structured_output_and_masks_secret():
    provider = OpenAICompatibleGenerationProvider(
        base_url='https://example.invalid/v1', api_key='top-secret', model_id='model', timeout_seconds=1,
    )
    content = GenerationDraft(
        status='grounded', claims=[GroundedClaim(text='확인해야 합니다.', citation_ids=['allowed'])]
    ).model_dump_json()
    response = type('Response', (), {'raise_for_status': lambda self: None, 'json': lambda self: {'choices': [{'message': {'content': content}}]}})()
    with patch('app.services.generation_provider.httpx.post', return_value=response):
        assert provider.generate('system', 'user').claims[0].citation_ids == ['allowed']
    malformed = type('Response', (), {'raise_for_status': lambda self: None, 'json': lambda self: {'choices': []}})()
    with patch('app.services.generation_provider.httpx.post', return_value=malformed):
        with pytest.raises(GenerationProviderUnavailable):
            provider.generate('system', 'user')
    with patch('app.services.generation_provider.httpx.post', side_effect=httpx.TimeoutException('top-secret')):
        with pytest.raises(GenerationProviderUnavailable) as exc:
            provider.generate('system', 'user')
    assert 'top-secret' not in str(exc.value)


def test_answer_api_is_additive_and_retrieve_api_remains_compatible(monkeypatch):
    _cleanup(); _seed()
    try:
        monkeypatch.setattr('app.api.legal_retrieval.production_generation_provider', lambda settings: DeterministicTestGenerationProvider())
        answer = client.post('/api/rag/answer', json={
            'question': '환경영향평가 대상', 'as_of': '2026-01-01', 'top_k': 5,
            'source_types': ['attached_table'], 'retrieval_mode': 'lexical',
        })
        assert answer.status_code == 200
        data = answer.json()
        assert data['status'] == 'grounded' and data['disclaimer']
        assert data['citations'][0]['source_type'] == 'attached_table'
        retrieve = client.post('/api/rag/retrieve', json={
            'query': '환경영향평가 대상', 'as_of': '2026-01-01', 'top_k': 5,
            'source_types': ['attached_table'],
        })
        assert retrieve.status_code == 200 and 'answer' not in retrieve.json()
    finally:
        _cleanup()
