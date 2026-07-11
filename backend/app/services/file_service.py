import mimetypes
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.file import BatchStatus, DocumentBatch, ParseDeadLetter, ParseStage, ParseStatus, ProjectFile
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.repositories.project_repository import ProjectRepository
from app.storage.storage_service import get_storage_service
from app.schemas.file import BatchCreateRequest, BatchRead, UploadSession
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

        filename = upload_file.filename or ""
        self._validate_filename(filename)
        content = upload_file.file.read(settings.max_upload_size_bytes + 1)
        if len(content) > settings.max_upload_size_bytes:
            raise HTTPException(status_code=413, detail="File exceeds the upload size limit")
        object_key = self._object_key(user.id, project_id, upload_file.filename)
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
            parse_stage=ParseStage.validate,
            progress=10,
        )

        parse_uploaded_file_task.delay(file.id)
        return file

    def create_batch(self, project_id: str, user: User, request: BatchCreateRequest) -> BatchRead:
        project = self.project_repo.get_for_owner(project_id, user.id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not request.files or len(request.files) > 100:
            raise HTTPException(status_code=400, detail="A batch must contain 1 to 100 files")
        if any(item.size > settings.max_upload_size_bytes for item in request.files):
            raise HTTPException(status_code=413, detail="File exceeds the upload size limit")
        for item in request.files:
            self._validate_filename(item.filename)
        batch = DocumentBatch(project_id=project_id, total_files=len(request.files), status=BatchStatus.uploading)
        self.db.add(batch)
        self.db.flush()
        sessions: list[UploadSession] = []
        for item in request.files:
            key = self._object_key(user.id, project_id, item.filename)
            plan = self.storage.create_upload_plan(key, item.size, item.content_type)
            file = ProjectFile(
                project_id=project_id, batch_id=batch.id, filename=item.filename,
                content_type=item.content_type, size=item.size, r2_bucket=getattr(self.storage, "bucket", None),
                r2_object_key=key, parse_status=ParseStatus.pending, parse_stage=ParseStage.upload, progress=0,
                multipart_upload_id=plan.upload_id, expected_checksum_sha256=item.checksum_sha256,
            )
            self.db.add(file)
            self.db.flush()
            sessions.append(UploadSession(
                file_id=file.id, object_key=key, upload_url=plan.upload_url, upload_mode=plan.upload_mode,
                part_size=plan.part_size, total_parts=plan.total_parts, upload_id=plan.upload_id,
            ))
        self.db.commit()
        files = list(self.db.query(ProjectFile).filter(ProjectFile.batch_id == batch.id).all())
        return BatchRead.model_validate({"id": batch.id, "project_id": project_id, "total_files": batch.total_files,
            "completed_files": 0, "failed_files": 0, "progress": 0, "status": batch.status,
            "files": files, "upload_sessions": sessions})

    def complete_batch(self, batch_id: str, user: User) -> BatchRead:
        batch = self.db.get(DocumentBatch, batch_id)
        if not batch or not self.project_repo.get_for_owner(batch.project_id, user.id):
            raise HTTPException(status_code=404, detail="Batch not found")
        files = list(self.db.query(ProjectFile).filter(ProjectFile.batch_id == batch.id).all())
        if batch.status != BatchStatus.uploading:
            return BatchRead.model_validate({"id": batch.id, "project_id": batch.project_id,
                "total_files": batch.total_files, "completed_files": batch.completed_files,
                "failed_files": batch.failed_files, "progress": batch.progress, "status": batch.status,
                "files": files, "upload_sessions": []})
        batch.status = BatchStatus.queued
        self.db.commit()
        queued_file_ids: list[str] = []
        for file in files:
            if not self.storage.object_exists(file.r2_object_key, file.size):
                file.parse_status = ParseStatus.failed
                file.parse_error = "Uploaded object is missing or size does not match"
                file.parse_stage = ParseStage.validate
                file.progress = 0
            else:
                file.parse_status = ParseStatus.pending
                file.parse_stage = ParseStage.validate
                file.progress = 10
                queued_file_ids.append(file.id)
        self.db.commit()
        from app.workers.tasks import _refresh_batch
        _refresh_batch(self.db, batch.id)
        for file_id in queued_file_ids:
            parse_uploaded_file_task.delay(file_id)
        return BatchRead.model_validate({"id": batch.id, "project_id": batch.project_id,
            "total_files": batch.total_files, "completed_files": batch.completed_files,
            "failed_files": batch.failed_files, "progress": batch.progress, "status": batch.status,
            "files": files, "upload_sessions": []})

    def get_batch(self, batch_id: str, user: User) -> BatchRead:
        batch = self.db.get(DocumentBatch, batch_id)
        if not batch or not self.project_repo.get_for_owner(batch.project_id, user.id):
            raise HTTPException(status_code=404, detail="Batch not found")
        files = list(self.db.query(ProjectFile).filter(ProjectFile.batch_id == batch.id).all())
        sessions: list[UploadSession] = []
        if batch.status == BatchStatus.uploading:
            for file in files:
                if file.multipart_upload_id:
                    sessions.append(UploadSession(
                        file_id=file.id, object_key=file.r2_object_key, upload_url=None,
                        upload_mode="multipart", part_size=settings.upload_part_size_bytes,
                        total_parts=(file.size + settings.upload_part_size_bytes - 1) // settings.upload_part_size_bytes,
                        upload_id=file.multipart_upload_id,
                    ))
                else:
                    sessions.append(UploadSession(
                        file_id=file.id, object_key=file.r2_object_key,
                        upload_url=self.storage.presign_upload_url(file.r2_object_key, file.content_type),
                        upload_mode="direct" if settings.r2_enabled else "backend",
                    ))
        return BatchRead.model_validate({
            "id": batch.id, "project_id": batch.project_id, "total_files": batch.total_files,
            "completed_files": batch.completed_files, "failed_files": batch.failed_files,
            "progress": batch.progress, "status": batch.status, "files": files,
            "upload_sessions": sessions,
        })

    def delete(self, file_id: str, user: User) -> None:
        file = self.file_repo.get(file_id)
        if not file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        project = self.project_repo.get_for_owner(file.project_id, user.id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        self.storage.delete_file(file.r2_object_key)
        self.file_repo.delete(file)

    def retry(self, file_id: str, user: User):
        file = self.file_repo.get(file_id)
        if not file or not self.project_repo.get_for_owner(file.project_id, user.id):
            raise HTTPException(status_code=404, detail="File not found")
        if file.parse_status != ParseStatus.failed:
            raise HTTPException(status_code=409, detail="Only failed files can be retried")
        if file.retry_count >= settings.max_parse_retries:
            raise HTTPException(status_code=409, detail="Maximum parse retries exceeded")
        file.parse_status = ParseStatus.pending
        file.parse_stage = ParseStage.validate
        file.progress = 10
        file.parse_error = None
        dead_letter = self.db.query(ParseDeadLetter).filter(ParseDeadLetter.file_id == file.id).one_or_none()
        if dead_letter:
            dead_letter.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        parse_uploaded_file_task.delay(file.id)
        return file

    @staticmethod
    def _validate_filename(filename: str) -> None:
        allowed = {"pdf", "doc", "docx", "xlsx", "xls", "csv", "txt", "md", "png", "jpg", "jpeg", "webp"}
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if not filename.strip() or suffix not in allowed:
            raise HTTPException(status_code=415, detail="Unsupported or missing file extension")

    @staticmethod
    def _object_key(owner_id: str, project_id: str, filename: str) -> str:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        safe_suffix = re.sub(r"[^a-z0-9]", "", suffix)[:10] or "bin"
        return f"tenants/{owner_id}/{project_id}/{uuid.uuid4()}.{safe_suffix}"
