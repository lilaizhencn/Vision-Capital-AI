from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embedding_service import EmbeddingService
from app.models.chunk import DocumentChunk


class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()

    def similarity_search(self, project_id: str, query: str, limit: int = 5) -> list[DocumentChunk]:
        query_embedding = self.embedding_service.embed_text(query)
        try:
            statement = (
                select(DocumentChunk)
                .where(DocumentChunk.project_id == project_id, DocumentChunk.embedding.is_not(None))
                .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
                .limit(limit)
            )
            results = list(self.db.scalars(statement))
            if results:
                return results
        except Exception:
            pass

        # pgvector 不可用或未生成 embedding 时，回退到最近文档片段，保证流程可运行。
        return list(
            self.db.scalars(
                select(DocumentChunk).where(DocumentChunk.project_id == project_id).order_by(DocumentChunk.created_at.desc()).limit(limit)
            )
        )

