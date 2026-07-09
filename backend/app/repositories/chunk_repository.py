from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk


class ChunkRepository:
    def __init__(self, db: Session):
        self.db = db

    def replace_for_file(self, file_id: str, chunks: list[DocumentChunk]) -> None:
        self.db.execute(delete(DocumentChunk).where(DocumentChunk.file_id == file_id))
        self.db.add_all(chunks)
        self.db.commit()

    def get_for_project(self, project_id: str, limit: int = 8) -> list[DocumentChunk]:
        return list(
            self.db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.project_id == project_id)
                .order_by(DocumentChunk.created_at.desc())
                .limit(limit)
            )
        )

