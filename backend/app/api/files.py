from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.file import FileRead, FileUploadResponse
from app.services.file_service import FileService

router = APIRouter(tags=["files"])


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
        return []
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
