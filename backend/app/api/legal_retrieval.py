from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.legal_retrieval import LegalRetrievalRequest, LegalRetrievalResponse
from app.services.hybrid_legal_retrieval_service import retrieve_with_mode

router = APIRouter(tags=["legal-retrieval"])


@router.post("/rag/retrieve", response_model=LegalRetrievalResponse)
def retrieve_legal_corpus(request: LegalRetrievalRequest, db: Session = Depends(get_db)) -> LegalRetrievalResponse:
    results, vector_status, fallback_used = retrieve_with_mode(
        db, request.query, request.as_of, request.top_k, request.source_types, request.retrieval_mode
    )
    strategy = "rrf_hybrid_v1" if request.retrieval_mode == "hybrid" and not fallback_used else "deterministic_lexical_v1"
    return LegalRetrievalResponse(
        query=request.query, as_of=request.as_of, top_k=request.top_k, results=results,
        retrieval_strategy=strategy, retrieval_mode=request.retrieval_mode,
        vector_status=vector_status, fallback_used=fallback_used,
    )
