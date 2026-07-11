import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embedding_service import EmbeddingService
from app.models.chunk import DocumentChunk
from app.models.file import ProjectFile
from app.models.project import Project


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

    def investment_strategy_search(self, project_id: str, query: str, limit: int = 24) -> list[DocumentChunk]:
        """Gather a broader evidence pack for investment-stage strategy questions."""
        candidates: list[DocumentChunk] = []
        seen: set[str] = set()
        file_counts: dict[str, int] = {}
        file_metadata = {
            file_id: (source_kind, extracted_data or {})
            for file_id, source_kind, extracted_data in self.db.execute(
                select(ProjectFile.id, ProjectFile.source_kind, ProjectFile.extracted_data)
                .where(ProjectFile.project_id == project_id)
            )
        }
        project_company = self.db.scalar(select(Project.company_name).where(Project.id == project_id)) or ""

        lowered = query.lower()
        skip_accounting_investments = any(marker in lowered for marker in ("投中", "交易", "投委", "仓位", "估值", "during"))

        def add(items: list[DocumentChunk], per_query_file_limit: int = 2) -> None:
            query_file_counts: dict[str, int] = {}
            for item in items:
                if item.id in seen:
                    continue
                source_kind, extracted_data = file_metadata.get(item.file_id, ("upload", {}))
                extracted_company = extracted_data.get("company") if isinstance(extracted_data, dict) else None
                if source_kind == "public_research" and extracted_company and not self._same_company(project_company, extracted_company):
                    continue
                per_file_limit = 8 if source_kind == "public_research" else 12
                if file_counts.get(item.file_id, 0) >= per_file_limit:
                    continue
                if query_file_counts.get(item.file_id, 0) >= per_query_file_limit:
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
                file_counts[item.file_id] = file_counts.get(item.file_id, 0) + 1
                query_file_counts[item.file_id] = query_file_counts.get(item.file_id, 0) + 1
                candidates.append(item)

        terms = [
            "ITEM 1. BUSINESS", "business segments", "consolidated statements of income", "revenue",
            "net income", "cash flow", "balance sheet", "customers", "competition", "risk factors", "management",
            "regulation", "industry", "market", "consumer spending", "financial stability",
            "manufacturing economy",
        ]

        for term in terms:
            statement = (
                select(DocumentChunk)
                .where(DocumentChunk.project_id == project_id, DocumentChunk.content.ilike(f"%{term}%"))
                .limit(40)
            )
            matches = sorted(
                self.db.scalars(statement),
                key=lambda chunk: self._term_chunk_score(chunk.content, term),
                reverse=True,
            )
            add(matches[:8], per_query_file_limit=1)
            if len(candidates) >= limit:
                break

        add(self.similarity_search(
            project_id,
            "business model segments revenue earnings cash flow balance sheet customers competition management regulation industry market risks",
            limit=limit,
        ))
        add(self.similarity_search(project_id, query, limit=limit))

        return candidates[:limit]

    @staticmethod
    def _term_chunk_score(content: str, term: str) -> int:
        lowered = content.lower()
        score = lowered.count(term.lower()) * 3
        if term.lower() in {"consolidated statements of income", "revenue", "net income", "cash flow", "balance sheet"}:
            score += sum(
                8 for marker in (
                    "consolidated statements", "years ended", "dollars in", "in millions",
                    "net sales", "total revenue", "operating income", "cash flows",
                ) if marker in lowered
            )
            score += min(8, len(re.findall(r"\d", content)) // 12)
            if "united states securities and exchange commission" in lowered:
                score -= 6
        if term.lower() == "risk factors" and "item 1a" in lowered:
            score += 10
        if term.lower() == "competition" and "competitive" in lowered:
            score += 6
        return score

    @classmethod
    def _same_company(cls, project_company: str, extracted_company: str) -> bool:
        left = cls._normalize_company(project_company)
        right = cls._normalize_company(extracted_company)
        return len(left) >= 4 and len(right) >= 4 and (left in right or right in left)

    @staticmethod
    def _normalize_company(value: str) -> str:
        value = re.sub(
            r"\b(incorporated|corporation|company|limited|holdings?|group|inc|corp|co|ltd|llc|plc)\.?\b",
            " ",
            value,
            flags=re.IGNORECASE,
        )
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())
