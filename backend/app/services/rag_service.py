from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embedding_service import EmbeddingService
from app.models.chunk import DocumentChunk


class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()

    def similarity_search(self, project_id: str, query: str, limit: int = 5) -> list[DocumentChunk]:
        try:
            query_embedding = self.embedding_service.embed_text(query)
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

    def investment_strategy_search(self, project_id: str, query: str, limit: int = 12) -> list[DocumentChunk]:
        """Gather a broader evidence pack for investment-stage strategy questions."""
        candidates: list[DocumentChunk] = []
        seen: set[str] = set()

        lowered = query.lower()
        skip_accounting_investments = any(marker in lowered for marker in ("投中", "交易", "投委", "仓位", "估值", "during"))

        def add(items: list[DocumentChunk]) -> None:
            for item in items:
                if item.id in seen:
                    continue
                item_text = item.content.lower()
                if skip_accounting_investments and any(term in item_text for term in (
                    "strategic investments are included",
                    "non-marketable equity securities",
                    "marketable equity securities are measured",
                    "other income (expense), net consists primarily",
                )):
                    continue
                seen.add(item.id)
                candidates.append(item)

        if any(marker in lowered for marker in ("投中", "交易", "投委", "仓位", "估值", "during")):
            terms = ["revenue", "gross margin", "remaining performance obligations", "competition", "risk factors", "cash flow", "customers", "consumption-based"]
        elif any(marker in lowered for marker in ("投后", "持有", "kpi", "退出", "post")):
            terms = ["revenue", "customers", "gross margin", "cash flow", "debt", "cybersecurity", "AI", "risk factors"]
        else:
            terms = ["ITEM 1. BUSINESS", "revenue", "customers", "competition", "risk factors", "gross margin", "remaining performance obligations"]

        for term in terms:
            statement = (
                select(DocumentChunk)
                .where(DocumentChunk.project_id == project_id, DocumentChunk.content.ilike(f"%{term}%"))
                .order_by(DocumentChunk.chunk_index.asc())
                .limit(2)
            )
            add(list(self.db.scalars(statement)))
            if len(candidates) >= limit:
                break

        add(self.similarity_search(
            project_id,
            "business model revenue growth gross margin customers remaining performance obligations competition risks cash flow AI product strategy",
            limit=limit,
        ))
        add(self.similarity_search(project_id, query, limit=limit))

        return candidates[:limit]
