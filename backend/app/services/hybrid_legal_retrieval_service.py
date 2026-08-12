from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session
from app.services.embedding_provider import EmbeddingProvider, EmbeddingProviderUnavailable
from app.services.legal_retrieval_service import build_legal_corpus, retrieve_legal_evidence
from app.services.postgres_legal_vector_repository import VectorBackendUnavailable


def retrieve_vector_evidence(db:Session,query:str,as_of:date,top_k:int,source_types,provider:EmbeddingProvider,index):
    corpus=build_legal_corpus(db,as_of,None if source_types is None else set(source_types))
    index.index_changed_sources(corpus,provider); vector=provider.embed_query(query)
    try: results=index.search(vector,provider.provider_id,top_k,model_id=provider.model_id,source_identifiers={item.source_identifier for item in corpus})
    except TypeError: results=index.search(vector,provider.provider_id,top_k)
    for rank,(item,score) in enumerate(results,1): item.vector_score=score; item.vector_rank=rank; item.relevance_score=score
    return [item for item,_ in results]


def retrieve_with_mode(db:Session,query:str,as_of:date,top_k:int,source_types=None,mode:str="lexical",provider=None,index=None):
    lexical=retrieve_legal_evidence(db,query,as_of,max(top_k,20),source_types)
    for rank,item in enumerate(lexical,1): item.lexical_score=item.relevance_score; item.lexical_rank=rank
    if mode=="lexical": return lexical[:top_k],"not_configured",False
    if provider is None or index is None: return lexical[:top_k],"unavailable",True
    try: vector=retrieve_vector_evidence(db,query,as_of,max(top_k,20),source_types,provider,index)
    except EmbeddingProviderUnavailable: return lexical[:top_k],"provider_unavailable",True
    except VectorBackendUnavailable: return lexical[:top_k],"backend_unavailable",True
    if mode=="vector": return vector[:top_k],"available",False
    by_id={item.citation_id:item for item in lexical}
    for item in vector: by_id.setdefault(item.citation_id,item)
    scores={key:0.0 for key in by_id}
    for rank,item in enumerate(lexical,1): scores[item.citation_id]+=1/(60+rank)
    for rank,item in enumerate(vector,1): scores[item.citation_id]+=1/(60+rank)
    fused=sorted(by_id.values(),key=lambda item:(-scores[item.citation_id],item.citation_id))
    for rank,item in enumerate(fused,1): item.fused_score=round(scores[item.citation_id],8); item.fused_rank=rank; item.relevance_score=item.fused_score
    return fused[:top_k],"available",False
