from __future__ import annotations
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.models.legal_source_embedding import LegalSourceEmbedding
from app.schemas.legal_retrieval import LegalRetrievalResult
from app.services.embedding_provider import EmbeddingProvider, EmbeddingProviderUnavailable

class VectorBackendUnavailable(RuntimeError): pass

def pgvector_capability(db: Session) -> bool:
    try: return db.execute(text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='vector')")).scalar_one()
    except SQLAlchemyError: return False

class PostgresLegalVectorRepository:
    def __init__(self, db: Session): self.db=db
    def index_changed_sources(self,documents,provider:EmbeddingProvider):
        wanted={item.source_identifier:item for item in documents}
        try:
            existing={row.source_identifier:row for row in self.db.scalars(select(LegalSourceEmbedding).where(LegalSourceEmbedding.provider_id==provider.provider_id,LegalSourceEmbedding.model_id==provider.model_id)).all()}
            changed=[item for key,item in wanted.items() if key not in existing or existing[key].content_hash!=item.content_hash or existing[key].embedding_dimension!=provider.dimension]
            vectors=provider.embed_documents([item.text for item in changed])
            for item,vector in zip(changed,vectors):
                values=dict(provider_id=provider.provider_id,model_id=provider.model_id,embedding_dimension=provider.dimension,source_type=item.source_type,source_identifier=item.source_identifier,law_identifier=item.law_identifier,law_name=item.law_name,title=item.title,source_text=item.text,text_excerpt=item.text_excerpt,effective_date=item.effective_date,version_status=item.version_status,mst=item.mst,provenance_json=item.provenance,citation_id=item.citation_id,content_hash=item.content_hash,embedding=vector)
                stmt=insert(LegalSourceEmbedding).values(**values).on_conflict_do_update(constraint="uq_legal_embedding_provider_source",set_={**values,"updated_at":text("now()")})
                self.db.execute(stmt)
            stale=set(existing)-set(wanted)
            if stale: self.db.execute(delete(LegalSourceEmbedding).where(LegalSourceEmbedding.provider_id==provider.provider_id,LegalSourceEmbedding.model_id==provider.model_id,LegalSourceEmbedding.source_identifier.in_(stale)))
            self.db.commit(); return {"indexed":len(changed),"unchanged":len(documents)-len(changed),"removed":len(stale)}
        except EmbeddingProviderUnavailable: self.db.rollback(); raise
        except SQLAlchemyError as exc: self.db.rollback(); raise VectorBackendUnavailable("Vector backend is unavailable.") from exc
    def search(self,query_vector,provider_id,top_k,model_id=None,source_identifiers=None):
        try:
            distance=LegalSourceEmbedding.embedding.cosine_distance(query_vector)
            stmt=select(LegalSourceEmbedding,distance.label("distance")).where(LegalSourceEmbedding.provider_id==provider_id,LegalSourceEmbedding.embedding_dimension==len(query_vector))
            if model_id: stmt=stmt.where(LegalSourceEmbedding.model_id==model_id)
            if source_identifiers is not None: stmt=stmt.where(LegalSourceEmbedding.source_identifier.in_(source_identifiers))
            rows=self.db.execute(stmt.order_by(distance).limit(top_k)).all(); results=[]
            for row,distance_value in rows:
                item=LegalRetrievalResult(source_type=row.source_type,law_identifier=row.law_identifier,law_name=row.law_name,source_identifier=row.source_identifier,title=row.title,text=row.source_text,text_excerpt=row.text_excerpt,effective_date=row.effective_date,version_status=row.version_status,mst=row.mst,provenance=row.provenance_json,citation_id=row.citation_id,content_hash=row.content_hash,relevance_score=0)
                results.append((item,round(1-float(distance_value),6)))
            return results
        except SQLAlchemyError as exc: self.db.rollback(); raise VectorBackendUnavailable("Vector backend is unavailable.") from exc
