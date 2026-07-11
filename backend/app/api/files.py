from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from math import ceil
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.deps import get_current_user
from app.models.file import DocumentBatch, ParseStage
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.file import BatchCreateRequest, BatchRead, FileRead, FileUploadResponse, MultipartCompleteRequest, MultipartPart
from app.services.file_service import FileService

router = APIRouter(tags=["files"])


@router.post("/api/projects/{project_id}/file-batches", response_model=BatchRead)
def create_file_batch(project_id: str, payload: BatchCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return FileService(db).create_batch(project_id, user, payload)


@router.post("/api/file-batches/{batch_id}/complete", response_model=BatchRead)
def complete_file_batch(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return FileService(db).complete_batch(batch_id, user)


@router.get("/api/file-batches/{batch_id}", response_model=BatchRead)
def get_file_batch(batch_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return FileService(db).get_batch(batch_id, user)


@router.post("/api/file-batches/{batch_id}/files/{file_id}/content", response_model=FileRead)
def upload_batch_file_content(batch_id: str, file_id: str, upload_file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = FileService(db)
    batch = db.get(DocumentBatch, batch_id)
    file = FileRepository(db).get(file_id)
    if not batch or not file or file.batch_id != batch_id or not ProjectRepository(db).get_for_owner(batch.project_id, user.id):
        raise HTTPException(status_code=404, detail="Batch file not found")
    content = upload_file.file.read(file.size + 1)
    if len(content) > file.size:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the declared size")
    if len(content) != file.size:
        raise HTTPException(status_code=400, detail="Uploaded size does not match the declared size")
    service.storage.upload_file(file.r2_object_key, content, upload_file.content_type)
    file.parse_stage = ParseStage.validate
    file.progress = 10
    db.commit()
    return file


@router.get("/api/file-batches/{batch_id}/files/{file_id}/parts/{part_number}/url")
def sign_multipart_part(batch_id: str, file_id: str, part_number: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file = FileRepository(db).get(file_id)
    batch = db.get(DocumentBatch, batch_id)
    if not batch or not file or file.batch_id != batch_id or not ProjectRepository(db).get_for_owner(batch.project_id, user.id):
        raise HTTPException(status_code=404, detail="Batch file not found")
    if not file.multipart_upload_id or not hasattr(FileService(db).storage, "presign_upload_part"):
        raise HTTPException(status_code=400, detail="Multipart upload is not available")
    total_parts = ceil(file.size / settings.upload_part_size_bytes)
    if part_number < 1 or part_number > total_parts:
        raise HTTPException(status_code=400, detail="Invalid multipart part number")
    return {"url": FileService(db).storage.presign_upload_part(file.r2_object_key, file.multipart_upload_id, part_number)}


@router.get("/api/file-batches/{batch_id}/files/{file_id}/parts")
def list_multipart_parts(batch_id: str, file_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file = FileRepository(db).get(file_id)
    batch = db.get(DocumentBatch, batch_id)
    storage = FileService(db).storage
    if not batch or not file or file.batch_id != batch_id or not ProjectRepository(db).get_for_owner(batch.project_id, user.id):
        raise HTTPException(status_code=404, detail="Batch file not found")
    if not file.multipart_upload_id or not hasattr(storage, "list_multipart_parts"):
        return {"parts": []}
    return {"parts": storage.list_multipart_parts(file.r2_object_key, file.multipart_upload_id)}


@router.post("/api/file-batches/{batch_id}/files/{file_id}/parts/{part_number}/content", response_model=MultipartPart)
def upload_multipart_part_content(
    batch_id: str,
    file_id: str,
    part_number: int,
    upload_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file = FileRepository(db).get(file_id)
    batch = db.get(DocumentBatch, batch_id)
    storage = FileService(db).storage
    if not batch or not file or file.batch_id != batch_id or not ProjectRepository(db).get_for_owner(batch.project_id, user.id):
        raise HTTPException(status_code=404, detail="Batch file not found")
    if not file.multipart_upload_id or not hasattr(storage, "upload_part"):
        raise HTTPException(status_code=400, detail="Multipart upload is not available")
    total_parts = ceil(file.size / settings.upload_part_size_bytes)
    if part_number < 1 or part_number > total_parts:
        raise HTTPException(status_code=400, detail="Invalid multipart part number")
    content = upload_file.file.read(settings.upload_part_size_bytes + 1)
    expected_size = min(settings.upload_part_size_bytes, file.size - (part_number - 1) * settings.upload_part_size_bytes)
    if len(content) != expected_size:
        raise HTTPException(status_code=400, detail="Uploaded part size does not match the declared size")
    etag = storage.upload_part(file.r2_object_key, file.multipart_upload_id, part_number, content)
    return MultipartPart(part_number=part_number, etag=etag)


@router.post("/api/file-batches/{batch_id}/files/{file_id}/complete-multipart")
def complete_multipart(batch_id: str, file_id: str, payload: MultipartCompleteRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file = FileRepository(db).get(file_id)
    batch = db.get(DocumentBatch, batch_id)
    if not batch or not file or file.batch_id != batch_id or not ProjectRepository(db).get_for_owner(batch.project_id, user.id):
        raise HTTPException(status_code=404, detail="Batch file not found")
    storage = FileService(db).storage
    if not file.multipart_upload_id or not hasattr(storage, "complete_multipart"):
        raise HTTPException(status_code=400, detail="Multipart upload is not available")
    total_parts = ceil(file.size / settings.upload_part_size_bytes)
    numbers = [part.part_number for part in payload.parts]
    if sorted(numbers) != list(range(1, total_parts + 1)):
        raise HTTPException(status_code=400, detail="All multipart parts are required exactly once")
    if any(not part.etag.strip() for part in payload.parts):
        raise HTTPException(status_code=400, detail="Every multipart part must include an ETag")
    storage.complete_multipart(file.r2_object_key, file.multipart_upload_id, [{"PartNumber": p.part_number, "ETag": p.etag} for p in payload.parts])
    file.parse_stage = ParseStage.validate
    file.progress = 10
    db.commit()
    return file


@router.post("/api/projects/{project_id}/files/upload", response_model=FileUploadResponse)
def upload_file(
    project_id: str,
    upload_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file = FileService(db).upload(project_id, user, upload_file)
    return FileUploadResponse(file=FileRead.model_validate(file), task_status=file.parse_status.value)


@router.get("/api/projects/{project_id}/files", response_model=list[FileRead])
def list_files(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = ProjectRepository(db).get_for_owner(project_id, user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return FileRepository(db).list_for_project(project_id)


@router.get("/api/files/{file_id}", response_model=FileRead)
def get_file(file_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file = FileRepository(db).get(file_id)
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    project = ProjectRepository(db).get_for_owner(file.project_id, user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return file


@router.delete("/api/files/{file_id}")
def delete_file(file_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    FileService(db).delete(file_id, user)
    return {"message": "File deleted"}


@router.post("/api/files/{file_id}/retry", response_model=FileRead)
def retry_file(file_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return FileService(db).retry(file_id, user)
