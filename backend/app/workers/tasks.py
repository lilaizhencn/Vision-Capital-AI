from app.ai.embedding_service import EmbeddingService
from app.core.database import SessionLocal
from app.models.chunk import DocumentChunk
from app.models.file import ParseStatus
from app.models.file import BatchStatus, ParseStage
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.file_repository import FileRepository
from app.rag.chunking import chunk_text, estimate_tokens
from app.services.document_parser_service import DocumentParserService
from app.storage.storage_service import get_storage_service
from app.workers.celery_app import celery_app


@celery_app.task(
    name="parse_uploaded_file_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_kwargs={"max_retries": 3},
)
def parse_uploaded_file_task(file_id: str) -> None:
    db = SessionLocal()
    try:
        file_repo = FileRepository(db)
        chunk_repo = ChunkRepository(db)
        storage = get_storage_service()
        parser = DocumentParserService()
        embedding_service = EmbeddingService()

        file = file_repo.get(file_id)
        if not file:
            return

        file.parse_status = ParseStatus.processing
        file.parse_stage = ParseStage.validate
        file.progress = 10
        file.parse_error = None
        db.commit()

        # 这里串起上传后最关键的数据管道：下载、解析、切片、向量化、入库。
        data = storage.download_file(file.r2_object_key)
        file.parse_stage = ParseStage.ocr
        file.progress = 35
        db.commit()
        text = parser.parse(file.filename, file.content_type, data)
        file.parse_stage = ParseStage.table_extract
        file.progress = 55
        db.commit()
        text_chunks = chunk_text(text)

        file.parse_stage = ParseStage.llm_extract
        file.progress = 75
        db.commit()
        records: list[DocumentChunk] = []
        for index, chunk in enumerate(text_chunks):
            embedding = None
            try:
                embedding = embedding_service.embed_text(chunk)
            except RuntimeError:
                embedding = None

            records.append(
                DocumentChunk(
                    project_id=file.project_id,
                    file_id=file.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=embedding,
                    token_count=estimate_tokens(chunk),
                )
            )

        file.parse_stage = ParseStage.persist
        file.progress = 90
        db.commit()
        chunk_repo.replace_for_file(file.id, records)
        file.parse_status = ParseStatus.completed
        file.parse_stage = ParseStage.completed
        file.progress = 100
        db.commit()
        _refresh_batch(db, file.batch_id)
    except Exception as exc:
        file = FileRepository(db).get(file_id)
        if file:
            file.parse_status = ParseStatus.failed
            file.parse_error = str(exc)
            file.progress = 0
            file.retry_count = (file.retry_count or 0) + 1
            db.commit()
            _refresh_batch(db, file.batch_id)
        raise
    finally:
        db.close()


def _refresh_batch(db, batch_id: str | None) -> None:
    if not batch_id:
        return
    from app.models.file import DocumentBatch, ProjectFile

    batch = db.get(DocumentBatch, batch_id)
    if not batch:
        return
    files = list(db.query(ProjectFile).filter(ProjectFile.batch_id == batch_id).all())
    batch.completed_files = sum(item.parse_status == ParseStatus.completed for item in files)
    batch.failed_files = sum(item.parse_status == ParseStatus.failed for item in files)
    batch.progress = round(sum(item.progress for item in files) / max(len(files), 1))
    if batch.failed_files == batch.total_files:
        batch.status = BatchStatus.failed
    elif batch.completed_files + batch.failed_files == batch.total_files:
        batch.status = BatchStatus.completed if batch.failed_files == 0 else BatchStatus.failed
    else:
        batch.status = BatchStatus.processing
    db.commit()
