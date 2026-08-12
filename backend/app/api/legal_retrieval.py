from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.legal_generation import LegalAnswerRequest, LegalAnswerResponse
from app.schemas.legal_retrieval import LegalRetrievalRequest, LegalRetrievalResponse
from app.services.embedding_provider import production_embedding_provider
from app.services.generation_provider import production_generation_provider
from app.services.grounded_legal_generation_service import answer_legal_question
from app.services.hybrid_legal_retrieval_service import retrieve_with_mode
from app.services.postgres_legal_vector_repository import PostgresLegalVectorRepository
router=APIRouter(tags=["legal-retrieval"])

@router.post("/rag/retrieve",response_model=LegalRetrievalResponse)
def retrieve_legal_corpus(request:LegalRetrievalRequest,db:Session=Depends(get_db))->LegalRetrievalResponse:
    provider=production_embedding_provider(get_settings()) if request.retrieval_mode!="lexical" else None
    repository=PostgresLegalVectorRepository(db) if provider is not None else None
    results,vector_status,fallback_used=retrieve_with_mode(db,request.query,request.as_of,request.top_k,request.source_types,request.retrieval_mode,provider,repository)
    strategy="rrf_hybrid_v1" if request.retrieval_mode=="hybrid" and not fallback_used else ("pgvector_cosine_v1" if request.retrieval_mode=="vector" and not fallback_used else "deterministic_lexical_v1")
    provider_status="available" if provider else "not_configured"
    backend_status="available" if vector_status=="available" else ("unavailable" if vector_status=="backend_unavailable" else "not_checked")
    return LegalRetrievalResponse(query=request.query,as_of=request.as_of,top_k=request.top_k,results=results,retrieval_strategy=strategy,retrieval_mode=request.retrieval_mode,vector_status=vector_status,provider_status=provider_status,backend_status=backend_status,fallback_used=fallback_used)


@router.post('/rag/answer', response_model=LegalAnswerResponse)
def answer_from_legal_corpus(request: LegalAnswerRequest, db: Session = Depends(get_db)) -> LegalAnswerResponse:
    settings = get_settings()
    return answer_legal_question(
        db=db, question=request.question, as_of=request.as_of, top_k=request.top_k,
        source_types=request.source_types, retrieval_mode=request.retrieval_mode,
        generation_provider=production_generation_provider(settings), settings=settings,
    )
