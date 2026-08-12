from __future__ import annotations

import json
import re
from datetime import date

from sqlalchemy.orm import Session

from app.schemas.legal_generation import GenerationDraft, LegalAnswerResponse, LegalCitation
from app.services.embedding_provider import production_embedding_provider
from app.services.generation_provider import GenerationProvider, GenerationProviderUnavailable
from app.services.hybrid_legal_retrieval_service import retrieve_with_mode
from app.services.postgres_legal_vector_repository import PostgresLegalVectorRepository


LEGAL_DISCLAIMER = (
    '이 분석은 제공된 법령 근거에 따른 참고용 정보이며 법적 유권해석이 아닙니다. '
    '실제 사업 적용 전 최신 법령 원문을 확인하고, 최종 판단은 인허가권자 또는 관련 전문가에게 확인해야 합니다.'
)

SYSTEM_PROMPT = '''당신은 대한민국 도시개발·인허가 실무를 지원하는 근거 제한형 법령 설명 도구입니다.
반드시 제공된 evidence만 사용하고 기억이나 일반 지식으로 법률적 사실, 법령명 또는 조문 번호를 보충하지 마십시오.
각 주요 주장은 claims 배열의 독립 항목으로 작성하고, 해당 evidence의 citation_id를 citation_ids에 하나 이상 연결하십시오.
citation_id를 새로 만들거나 claim text에 직접 citation 표기를 넣지 마십시오.
근거가 부족하면 status를 insufficient_evidence로 하고 claims를 비우십시오.
근거가 충돌하면 하나를 임의 선택하지 말고 status를 conflicting_evidence로 하며 warnings에 충돌 내용을 기록하십시오.
historical/current/future version을 혼용하지 말고, attached_table도 article과 동일한 근거로 취급하십시오.
유권해석처럼 단정하지 말고 자연스러운 한국 도시개발·인허가 실무 표현을 사용하십시오.
JSON 객체만 반환하십시오. 필드는 status, claims, warnings이며 각 claim 필드는 text와 citation_ids입니다.'''


def build_generation_prompt(question: str, as_of: date, evidence) -> str:
    rows = [
        {
            'citation_id': item.citation_id,
            'law_identifier': item.law_identifier,
            'law_name': item.law_name,
            'source_type': item.source_type,
            'source_identifier': item.source_identifier,
            'title': item.title,
            'effective_date': item.effective_date.isoformat(),
            'mst': item.mst,
            'provenance': item.provenance,
            'excerpt': item.text_excerpt,
            'content_hash': item.content_hash,
        }
        for item in evidence
    ]
    return json.dumps({'question': question, 'as_of': as_of.isoformat(), 'evidence': rows}, ensure_ascii=False)


def _citation(item) -> LegalCitation:
    return LegalCitation(
        citation_id=item.citation_id, law_identifier=item.law_identifier, law_name=item.law_name,
        source_type=item.source_type, source_identifier=item.source_identifier, title=item.title,
        effective_date=item.effective_date, mst=item.mst, provenance=item.provenance,
        excerpt=item.text_excerpt, content_hash=item.content_hash,
    )


def validate_grounded_draft(draft: GenerationDraft, evidence):
    allowed = {item.citation_id: item for item in evidence}
    if draft.status == 'insufficient_evidence':
        if draft.claims:
            raise ValueError('An insufficient-evidence response cannot contain claims.')
        return [], []
    if not draft.claims:
        raise ValueError('A grounded response must contain claims.')
    used: list[str] = []
    for claim in draft.claims:
        if 'law:' in claim.text.lower() or re.search(r'\[[^\]]*(?:citation|cit-|law:)[^\]]*\]', claim.text, re.IGNORECASE):
            raise ValueError('Citation markup is controlled by the system.')
        if not claim.citation_ids or any(citation_id not in allowed for citation_id in claim.citation_ids):
            raise ValueError('The provider returned a citation outside the allowed evidence set.')
        used.extend(claim.citation_ids)
    unique_ids = list(dict.fromkeys(used))
    return draft.claims, [_citation(allowed[citation_id]) for citation_id in unique_ids]


def _render_answer(claims) -> str:
    return '\n'.join(f'{claim.text} ' + ' '.join(f'[{citation_id}]' for citation_id in claim.citation_ids) for claim in claims)


def answer_legal_question(
    db: Session, question: str, as_of: date, top_k: int, source_types, retrieval_mode: str,
    generation_provider: GenerationProvider | None, settings, embedding_provider=None, vector_repository=None,
) -> LegalAnswerResponse:
    if retrieval_mode != 'lexical' and embedding_provider is None:
        embedding_provider = production_embedding_provider(settings)
    if embedding_provider is not None and vector_repository is None:
        vector_repository = PostgresLegalVectorRepository(db)
    evidence, retrieval_status, retrieval_fallback = retrieve_with_mode(
        db, question, as_of, top_k, source_types, retrieval_mode, embedding_provider, vector_repository
    )
    common = dict(
        evidence=evidence, as_of=as_of, retrieval_mode=retrieval_mode, retrieval_status=retrieval_status,
        retrieval_fallback_used=retrieval_fallback, disclaimer=LEGAL_DISCLAIMER,
    )
    if not evidence:
        return LegalAnswerResponse(
            status='insufficient_evidence', answer='현재 확보된 법령 근거만으로는 해당 사항을 확정하기 어렵습니다.',
            generation_status='not_invoked', provider_status='available' if generation_provider else 'not_configured',
            warnings=['질문에 직접 연결되는 검색 근거가 없습니다.'], **common,
        )
    if generation_provider is None:
        return LegalAnswerResponse(
            status='generation_unavailable', generation_status='unavailable', provider_status='not_configured',
            warnings=['답변 생성 provider가 설정되지 않아 검색 근거만 반환합니다.'], **common,
        )
    try:
        draft = generation_provider.generate(SYSTEM_PROMPT, build_generation_prompt(question, as_of, evidence))
    except GenerationProviderUnavailable:
        return LegalAnswerResponse(
            status='generation_unavailable', generation_status='unavailable', provider_status='unavailable',
            warnings=['답변 생성 provider를 사용할 수 없어 검색 근거만 반환합니다.'], **common,
        )
    try:
        claims, citations = validate_grounded_draft(draft, evidence)
    except ValueError:
        return LegalAnswerResponse(
            status='validation_failed', generation_status='invalid_grounding', provider_status='available',
            warnings=['생성 결과가 citation 검증을 통과하지 못해 답변을 차단했습니다.'], **common,
        )
    if draft.status == 'insufficient_evidence':
        return LegalAnswerResponse(
            status='insufficient_evidence', answer='현재 확보된 법령 근거만으로는 해당 사항을 확정하기 어렵습니다.',
            generation_status='completed', provider_status='available', warnings=draft.warnings, **common,
        )
    status = 'grounded_with_conflicts' if draft.status == 'conflicting_evidence' else 'grounded'
    warnings = draft.warnings or (['근거 간 추가 검토가 필요합니다.'] if status == 'grounded_with_conflicts' else [])
    return LegalAnswerResponse(
        status=status, answer=_render_answer(claims), claims=claims, citations=citations,
        generation_status='completed', provider_status='available', warnings=warnings, **common,
    )
