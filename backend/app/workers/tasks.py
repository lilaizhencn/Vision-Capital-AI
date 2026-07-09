from app.ai.embedding_service import EmbeddingService
from app.core.database import SessionLocal
from app.models.chunk import DocumentChunk
from app.models.file import ParseStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.file_repository import FileRepository
from app.rag.chunking import chunk_text, estimate_tokens
from app.services.document_parser_service import DocumentParserService
from app.storage.storage_service import get_storage_service
from app.workers.celery_app import celery_app


@celery_app.task(name="parse_uploaded_file_task")
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
        file.parse_error = None
        db.commit()

        # 这里串起上传后最关键的数据管道：下载、解析、切片、向量化、入库。
        data = storage.download_file(file.r2_object_key)
        text = parser.parse(file.filename, file.content_type, data)
        text_chunks = chunk_text(text)

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

        chunk_repo.replace_for_file(file.id, records)
        file.parse_status = ParseStatus.completed
        db.commit()
    except Exception as exc:
        file = FileRepository(db).get(file_id)
        if file:
            file.parse_status = ParseStatus.failed
            file.parse_error = str(exc)
            db.commit()
        raise
    finally:
        db.close()

