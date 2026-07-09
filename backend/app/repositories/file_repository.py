from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file import ProjectFile


class FileRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **data) -> ProjectFile:
        item = ProjectFile(**data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get(self, file_id: str) -> ProjectFile | None:
        return self.db.get(ProjectFile, file_id)

    def list_for_project(self, project_id: str) -> list[ProjectFile]:
        return list(
            self.db.scalars(
                select(ProjectFile).where(ProjectFile.project_id == project_id).order_by(ProjectFile.created_at.desc())
            )
        )

    def delete(self, file: ProjectFile) -> None:
        self.db.delete(file)
        self.db.commit()

