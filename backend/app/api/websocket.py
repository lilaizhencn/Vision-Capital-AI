import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import SessionLocal
from app.core.security import decode_token
from app.models.file import DocumentBatch
from app.repositories.project_repository import ProjectRepository

router = APIRouter(tags=["realtime"])


@router.websocket("/api/ws/batches/{batch_id}")
async def batch_progress(websocket: WebSocket, batch_id: str, token: str):
    await websocket.accept()
    db = SessionLocal()
    try:
        try:
            user_id = decode_token(token).get("sub")
        except ValueError:
            await websocket.close(code=4401)
            return
        batch = db.get(DocumentBatch, batch_id)
        if not batch or not ProjectRepository(db).get_for_owner(batch.project_id, user_id):
            await websocket.close(code=4404)
            return
        last_payload = None
        while True:
            db.expire_all()
            batch = db.get(DocumentBatch, batch_id)
            files = list(batch.project.files) if batch and batch.project else []
            payload = {
                "batch_id": batch_id,
                "status": batch.status.value if batch else "failed",
                "progress": batch.progress if batch else 0,
                "completed_files": batch.completed_files if batch else 0,
                "failed_files": batch.failed_files if batch else 0,
                "files": [{"id": f.id, "filename": f.filename, "status": f.parse_status.value,
                           "stage": f.parse_stage.value, "progress": f.progress, "error": f.parse_error}
                           for f in files if f.batch_id == batch_id],
            }
            if payload != last_payload:
                await websocket.send_json(payload)
                last_payload = payload
            if not batch or payload["status"] in {"completed", "failed"}:
                await asyncio.sleep(0.5)
                return
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
    finally:
        db.close()
