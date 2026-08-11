from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.legal_retrieval import LegalRetrievalRequest, LegalRetrievalResponse
from app.services.legal_retrieval_service import retrieve_legal_evidence

router = APIRouter(tags=["legal-retrieval"])


@router.post("/rag/retrieve", response_model=LegalRetrievalResponse)
def retrieve_legal_corpus(request: LegalRetrievalRequest, db: Session = Depends(get_db)) -> LegalRetrievalResponse:
    results = retrieve_legal_evidence(db, request.query, request.as_of, request.top_k, request.source_types)
    return LegalRetrievalResponse(query=request.query, as_of=request.as_of, top_k=request.top_k, results=results)
