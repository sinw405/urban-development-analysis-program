from __future__ import annotations

import yaml
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.legal_generation import LegalAnswerResponse
from app.schemas.legal_retrieval import LegalRetrievalResult


EvaluationCategory = Literal[
    'direct_article', 'procedure', 'attached_table', 'historical', 'current',
    'future_leakage', 'insufficient', 'conflict', 'citation_attack', 'unrelated',
]


class LegalRagEvaluationCase(BaseModel):
    case_id: str = Field(..., min_length=1)
    category: EvaluationCategory
    question: str = Field(..., min_length=1)
    as_of: date
    source_types: list[Literal['article', 'attached_table']] | None = None
    retrieval_mode: Literal['lexical', 'vector', 'hybrid'] = 'lexical'
    top_k: int = Field(default=5, ge=1, le=50)
    expected_law_identifiers: list[str] = Field(default_factory=list)
    expected_source_types: list[Literal['article', 'attached_table']] = Field(default_factory=list)
    expected_citation_ids: list[str] = Field(default_factory=list)
    expected_citation_contains: list[str] = Field(default_factory=list)
    forbidden_source_identifiers: list[str] = Field(default_factory=list)
    forbidden_content_contains: list[str] = Field(default_factory=list)
    expected_behavior: Literal['grounded', 'conflicting_evidence', 'insufficient_evidence', 'validation_failed', 'generation_unavailable']
    expected_abstention: bool = False
    attached_table_expected: bool = False
    notes: str = ''

    @model_validator(mode='after')
    def validate_expectations(self):
        if self.attached_table_expected and 'attached_table' not in self.expected_source_types:
            raise ValueError('Attached-table cases must expect the attached_table source type.')
        return self


class RetrievalEvaluationResult(BaseModel):
    case_id: str
    retrieval_mode: str
    passed: bool
    expected_evidence_hit_at_k: bool
    expected_source_hit_at_k: bool
    attached_table_hit: bool | None = None
    expected_rank: int | None = None
    recall_at_k: float
    reciprocal_rank: float
    citation_metadata_complete: bool
    forbidden_source_leakage: list[str] = Field(default_factory=list)
    forbidden_content_leakage: list[str] = Field(default_factory=list)
    retrieved_citation_ids: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)


class GenerationEvaluationResult(BaseModel):
    case_id: str
    passed: bool
    status: str
    citation_allow_list_valid: bool
    citation_metadata_complete: bool
    as_of_consistent: bool
    attached_table_preserved: bool | None = None
    abstention_correct: bool
    disclaimer_present: bool
    evidence_preserved: bool
    failure_reasons: list[str] = Field(default_factory=list)


class ModeComparisonResult(BaseModel):
    case_id: str
    results: dict[str, RetrievalEvaluationResult]


class EvaluationReport(BaseModel):
    total_cases: int
    passed: int
    failed: int
    category_results: dict[str, dict[str, int]]
    mode_results: dict[str, dict[str, int]]
    citation_failures: int
    as_of_failures: int
    attached_table_failures: int
    abstention_failures: int
    generation_failures: int
    blocker: list[str]
    quality_gate_passed: bool


class ProductionProviderReadiness(BaseModel):
    configured: bool
    provider_valid: bool
    model_present: bool
    base_url_present: bool
    api_key_present: bool
    timeout_valid: bool
    json_response_mode: bool = True
    test_provider_isolated: bool
    live_test_status: Literal['not_configured', 'pending_opt_in']


def load_evaluation_cases(path: str | Path) -> list[LegalRagEvaluationCase]:
    payload = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    return [LegalRagEvaluationCase.model_validate(item) for item in payload['cases']]


def _retrieval_metadata_complete(item: LegalRetrievalResult) -> bool:
    return bool(
        item.citation_id and item.law_identifier and item.law_name and item.source_type and
        item.source_identifier and item.title and item.effective_date and item.provenance is not None and
        item.text_excerpt and item.content_hash and len(item.content_hash) == 64
    )


def evaluate_retrieval(case: LegalRagEvaluationCase, results: list[LegalRetrievalResult], mode: str | None = None) -> RetrievalEvaluationResult:
    citations = [item.citation_id for item in results]
    expected_matches = [
        index for index, item in enumerate(results, 1)
        if item.law_identifier in case.expected_law_identifiers
        or item.citation_id in case.expected_citation_ids
        or any(fragment in item.citation_id for fragment in case.expected_citation_contains)
    ]
    expected_count = len(case.expected_citation_ids) + len(case.expected_citation_contains)
    if not expected_count:
        expected_count = len(case.expected_law_identifiers)
    hit_count = sum(
        1 for expected in case.expected_citation_ids if expected in citations
    ) + sum(
        1 for fragment in case.expected_citation_contains if any(fragment in citation for citation in citations)
    ) + sum(
        1 for law_id in case.expected_law_identifiers if any(item.law_identifier == law_id for item in results)
    )
    expected_hit = bool(expected_matches) if expected_count else (not results if case.expected_abstention else True)
    source_hit = all(any(item.source_type == source_type for item in results) for source_type in case.expected_source_types)
    attached_hit = any(item.source_type == 'attached_table' for item in results) if case.attached_table_expected else None
    forbidden_sources = [item.source_identifier for item in results if item.source_identifier in case.forbidden_source_identifiers]
    forbidden_content = [term for term in case.forbidden_content_contains if any(term in item.text for item in results)]
    metadata_complete = all(_retrieval_metadata_complete(item) for item in results)
    reasons = []
    if not expected_hit: reasons.append('expected_evidence_missing')
    if not source_hit: reasons.append('expected_source_type_missing')
    if attached_hit is False: reasons.append('attached_table_missing')
    if forbidden_sources: reasons.append('forbidden_source_leakage')
    if forbidden_content: reasons.append('forbidden_content_leakage')
    if not metadata_complete: reasons.append('citation_metadata_incomplete')
    if case.expected_abstention and results: reasons.append('expected_empty_result')
    return RetrievalEvaluationResult(
        case_id=case.case_id, retrieval_mode=mode or case.retrieval_mode, passed=not reasons,
        expected_evidence_hit_at_k=expected_hit, expected_source_hit_at_k=source_hit,
        attached_table_hit=attached_hit, expected_rank=min(expected_matches) if expected_matches else None,
        recall_at_k=round(min(hit_count / expected_count, 1.0), 6) if expected_count else (1.0 if not results else 0.0),
        reciprocal_rank=round(1 / min(expected_matches), 6) if expected_matches else 0.0,
        citation_metadata_complete=metadata_complete, forbidden_source_leakage=forbidden_sources,
        forbidden_content_leakage=forbidden_content, retrieved_citation_ids=citations, failure_reasons=reasons,
    )


def compare_retrieval_modes(case: LegalRagEvaluationCase, runner: Callable[[str], list[LegalRetrievalResult]]) -> ModeComparisonResult:
    return ModeComparisonResult(
        case_id=case.case_id,
        results={mode: evaluate_retrieval(case, runner(mode), mode) for mode in ('lexical', 'vector', 'hybrid')},
    )


def _citation_metadata_complete(citation) -> bool:
    return bool(
        citation.citation_id and citation.law_identifier and citation.law_name and citation.source_type and
        citation.source_identifier and citation.title and citation.effective_date and citation.provenance is not None and
        citation.excerpt and citation.content_hash and len(citation.content_hash) == 64
    )


def evaluate_generation(case: LegalRagEvaluationCase, response: LegalAnswerResponse) -> GenerationEvaluationResult:
    allowed = {item.citation_id for item in response.evidence}
    claimed = {citation_id for claim in response.claims for citation_id in claim.citation_ids}
    citation_ids = {item.citation_id for item in response.citations}
    allow_list_valid = claimed <= allowed and citation_ids <= allowed
    metadata_complete = all(_citation_metadata_complete(item) for item in response.citations)
    as_of_consistent = response.as_of == case.as_of and all(item.effective_date <= case.as_of for item in response.evidence)
    table_preserved = None
    if case.attached_table_expected:
        table_preserved = bool(response.citations) and all(item.source_type == 'attached_table' and ':table:' in item.citation_id for item in response.citations)
    abstention_statuses = {'insufficient_evidence', 'validation_failed', 'generation_unavailable'}
    abstention_correct = (response.status in abstention_statuses and not response.claims) if case.expected_abstention else response.status not in {'insufficient_evidence'}
    expected_status = 'grounded_with_conflicts' if case.expected_behavior == 'conflicting_evidence' else case.expected_behavior
    status_correct = response.status == expected_status
    evidence_preserved = bool(response.evidence) if response.status in {'validation_failed', 'generation_unavailable'} else True
    reasons = []
    if not allow_list_valid: reasons.append('citation_hallucination')
    if not metadata_complete: reasons.append('citation_metadata_incomplete')
    if not as_of_consistent: reasons.append('as_of_leakage')
    if table_preserved is False: reasons.append('attached_table_provenance_loss')
    if not abstention_correct: reasons.append('abstention_incorrect')
    if not status_correct: reasons.append('unexpected_generation_status')
    if not response.disclaimer: reasons.append('disclaimer_missing')
    if not evidence_preserved: reasons.append('evidence_not_preserved')
    return GenerationEvaluationResult(
        case_id=case.case_id, passed=not reasons, status=response.status,
        citation_allow_list_valid=allow_list_valid, citation_metadata_complete=metadata_complete,
        as_of_consistent=as_of_consistent, attached_table_preserved=table_preserved,
        abstention_correct=abstention_correct, disclaimer_present=bool(response.disclaimer),
        evidence_preserved=evidence_preserved, failure_reasons=reasons,
    )


def build_evaluation_report(cases: list[LegalRagEvaluationCase], retrieval_results=(), generation_results=()) -> EvaluationReport:
    all_results = list(retrieval_results) + list(generation_results)
    case_categories = {case.case_id: case.category for case in cases}
    category_counts: dict[str, Counter] = {}
    mode_counts: dict[str, Counter] = {}
    for result in all_results:
        category_counts.setdefault(case_categories[result.case_id], Counter())[('passed' if result.passed else 'failed')] += 1
        if isinstance(result, RetrievalEvaluationResult):
            mode_counts.setdefault(result.retrieval_mode, Counter())[('passed' if result.passed else 'failed')] += 1
    blockers = [f'{result.case_id}:{reason}' for result in all_results for reason in result.failure_reasons]
    return EvaluationReport(
        total_cases=len(cases), passed=sum(result.passed for result in all_results), failed=sum(not result.passed for result in all_results),
        category_results={key: dict(value) for key, value in category_counts.items()},
        mode_results={key: dict(value) for key, value in mode_counts.items()},
        citation_failures=sum(any('citation' in reason for reason in result.failure_reasons) for result in all_results),
        as_of_failures=sum('as_of_leakage' in result.failure_reasons or 'forbidden_content_leakage' in result.failure_reasons for result in all_results),
        attached_table_failures=sum(any('attached_table' in reason for reason in result.failure_reasons) for result in all_results),
        abstention_failures=sum('abstention_incorrect' in result.failure_reasons or 'expected_empty_result' in result.failure_reasons for result in all_results),
        generation_failures=sum(not result.passed for result in generation_results), blocker=blockers,
        quality_gate_passed=not blockers,
    )


def production_provider_readiness(settings) -> ProductionProviderReadiness:
    provider_valid = settings.generation_provider in {'', 'openai-compatible'}
    configured = settings.generation_configured
    return ProductionProviderReadiness(
        configured=configured, provider_valid=provider_valid, model_present=bool(settings.generation_model),
        base_url_present=bool(settings.generation_base_url), api_key_present=bool(settings.generation_api_key),
        timeout_valid=settings.generation_timeout_seconds > 0, test_provider_isolated=settings.generation_provider != 'deterministic-test-only-v1',
        live_test_status='pending_opt_in' if configured else 'not_configured',
    )
