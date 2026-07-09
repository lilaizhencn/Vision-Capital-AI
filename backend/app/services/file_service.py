import mimetypes
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.file import ParseStatus
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.repositories.project_repository import ProjectRepository
from app.storage.storage_service import get_storage_service
from app.workers.tasks import parse_uploaded_file_task


class FileService:
    def __init__(self, db: Session):
        self.db = db
        self.file_repo = FileRepository(db)
        self.project_repo = ProjectRepository(db)
        self.storage = get_storage_service()

    def upload(self, project_id: str, user: User, upload_file: UploadFile):
        project = self.project_repo.get_for_owner(project_id, user.id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        content = upload_file.file.read()
        object_key = f"{project_id}/{uuid.uuid4()}-{upload_file.filename}"
        content_type = upload_file.content_type or mimetypes.guess_type(upload_file.filename)[0] or "application/octet-stream"
        stored = self.storage.upload_file(object_key=object_key, content=content, content_type=content_type)

        file = self.file_repo.create(
            project_id=project_id,
            filename=upload_file.filename,
            content_type=content_type,
            size=len(content),
            r2_bucket=stored.bucket,
            r2_object_key=stored.object_key,
            parse_status=ParseStatus.pending,
        )

        parse_uploaded_file_task.delay(file.id)
        return file

    def delete(self, file_id: str, user: User) -> None:
        file = self.file_repo.get(file_id)
        if not file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        project = self.project_repo.get_for_owner(file.project_id, user.id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        self.storage.delete_file(file.r2_object_key)
        self.file_repo.delete(file)

