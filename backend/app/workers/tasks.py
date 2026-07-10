from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from celery import chain
from botocore.exceptions import EndpointConnectionError, ReadTimeoutError
from openai import APIConnectionError, RateLimitError
from sqlalchemy.orm import Session

from app.ai.embedding_service import EmbeddingService
from app.ai.llm_service import LLMService
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.chunk import DocumentChunk
from app.models.file import BatchStatus, DocumentBatch, ParseDeadLetter, ParseStage, ParseStageRun, ParseStatus, ProjectFile
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.file_repository import FileRepository
from app.rag.chunking import chunk_text, estimate_tokens
from app.services.document_parser_service import DocumentParserService
from app.services.file_validation_service import validate_file_signature
from app.services.virus_scan_service import VirusScanner
from app.storage.storage_service import get_storage_service
from app.workers.celery_app import celery_app


RETRYABLE_ERRORS = (ConnectionError, TimeoutError, EndpointConnectionError, ReadTimeoutError, APIConnectionError, RateLimitError)
STAGE_PROGRESS = {
    ParseStage.validate: 10,
    ParseStage.ocr: 20,
    ParseStage.table_extract: 60,
    ParseStage.llm_extract: 80,
    ParseStage.persist: 95,
}


@celery_app.task(name="parse_uploaded_file_task")
def parse_uploaded_file_task(file_id: str):
    """Dispatch independent validation, OCR, table, LLM, and persist stages."""
    workflow = chain(
        validate_uploaded_file_task.s(file_id),
        ocr_document_task.s(),
        extract_document_tables_task.s(),
        extract_document_data_task.s(),
        persist_document_task.s(),
    )
    if settings.celery_task_always_eager:
        return workflow.apply()
    return workflow.apply_async()


@celery_app.task(bind=True, name="validate_uploaded_file_task", autoretry_for=RETRYABLE_ERRORS, retry_backoff=True, retry_backoff_max=120, retry_kwargs={"max_retries": settings.max_parse_retries})
def validate_uploaded_file_task(self, file_id: str):
    db = SessionLocal()
    try:
        file = _begin_stage(db, file_id, ParseStage.validate)
        if not file:
            return file_id
        with TemporaryDirectory(prefix="vision-validate-") as directory:
            path = Path(directory) / "object"
            get_storage_service().download_file_to_path(file.r2_object_key, path)
            if path.stat().st_size != file.size:
                raise ValueError("Uploaded object is missing or size does not match")
            with path.open("rb") as source:
                header = source.read(32)
            checksum = _sha256_file(path)
            if file.expected_checksum_sha256 and checksum.lower() != file.expected_checksum_sha256.lower():
                raise ValueError("Uploaded object checksum does not match the client-declared SHA-256")
            validate_file_signature(file.filename, header)
            file.checksum_sha256 = checksum
            scan_result = VirusScanner().scan_file(path)
        file.virus_scan_status = "clean" if scan_result != "skipped" else "skipped"
        file.virus_scan_result = scan_result
        _finish_stage(db, file, ParseStage.ocr, STAGE_PROGRESS[ParseStage.ocr])
        return file_id
    except Exception as exc:
        _fail_stage(db, file_id, ParseStage.validate, exc, self)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="ocr_document_task", autoretry_for=RETRYABLE_ERRORS, retry_backoff=True, retry_backoff_max=120, retry_kwargs={"max_retries": settings.max_parse_retries})
def ocr_document_task(self, file_id: str):
    db = SessionLocal()
    try:
        file = _begin_stage(db, file_id, ParseStage.ocr)
        if not file:
            return file_id
        with TemporaryDirectory(prefix="vision-ocr-") as directory:
            path = Path(directory) / "object"
            get_storage_service().download_file_to_path(file.r2_object_key, path)
            file.parsed_text = DocumentParserService().extract_text(file.filename, file.content_type, path)
        _finish_stage(db, file, ParseStage.table_extract, STAGE_PROGRESS[ParseStage.table_extract])
        return file_id
    except Exception as exc:
        _fail_stage(db, file_id, ParseStage.ocr, exc, self)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="extract_document_tables_task", autoretry_for=RETRYABLE_ERRORS, retry_backoff=True, retry_backoff_max=120, retry_kwargs={"max_retries": settings.max_parse_retries})
def extract_document_tables_task(self, file_id: str):
    db = SessionLocal()
    try:
        file = _begin_stage(db, file_id, ParseStage.table_extract)
        if not file:
            return file_id
        with TemporaryDirectory(prefix="vision-tables-") as directory:
            path = Path(directory) / "object"
            get_storage_service().download_file_to_path(file.r2_object_key, path)
            file.table_text = DocumentParserService().extract_table_text(file.filename, file.content_type, path)
        _finish_stage(db, file, ParseStage.llm_extract, STAGE_PROGRESS[ParseStage.llm_extract])
        return file_id
    except Exception as exc:
        _fail_stage(db, file_id, ParseStage.table_extract, exc, self)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="extract_document_data_task", autoretry_for=RETRYABLE_ERRORS, retry_backoff=True, retry_backoff_max=120, retry_kwargs={"max_retries": settings.max_parse_retries})
def extract_document_data_task(self, file_id: str):
    db = SessionLocal()
    try:
        file = _begin_stage(db, file_id, ParseStage.llm_extract)
        if not file:
            return file_id
        text = "\n\n".join(item for item in (file.parsed_text, file.table_text) if item)
        try:
            file.extracted_data = LLMService().extract_document_data(text)
        except RuntimeError:
            file.extracted_data = None
        _finish_stage(db, file, ParseStage.persist, STAGE_PROGRESS[ParseStage.persist])
        return file_id
    except Exception as exc:
        _fail_stage(db, file_id, ParseStage.llm_extract, exc, self)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="persist_document_task", autoretry_for=RETRYABLE_ERRORS, retry_backoff=True, retry_backoff_max=120, retry_kwargs={"max_retries": settings.max_parse_retries})
def persist_document_task(self, file_id: str):
    db = SessionLocal()
    try:
        file = _begin_stage(db, file_id, ParseStage.persist)
        if not file:
            return file_id
        text = "\n\n".join(item for item in (file.parsed_text, file.table_text) if item)
        records: list[DocumentChunk] = []
        for index, chunk in enumerate(chunk_text(text)):
            embedding = None
            try:
                embedding = EmbeddingService().embed_text(chunk)
            except Exception:
                # Embedding providers are optional for ingestion. The RAG layer
                # falls back to recent project chunks when vectorization is unavailable.
                pass
            records.append(DocumentChunk(project_id=file.project_id, file_id=file.id, chunk_index=index, content=chunk, embedding=embedding, token_count=estimate_tokens(chunk)))
        ChunkRepository(db).replace_for_file(file.id, records)
        file.parse_status = ParseStatus.completed
        file.parse_stage = ParseStage.completed
        file.progress = 100
        _complete_stage(db, file.id, ParseStage.persist)
        db.commit()
        _refresh_batch(db, file.batch_id)
        return file_id
    except Exception as exc:
        _fail_stage(db, file_id, ParseStage.persist, exc, self)
        raise
    finally:
        db.close()


def _begin_stage(db: Session, file_id: str, stage: ParseStage) -> ProjectFile | None:
    file = FileRepository(db).get(file_id)
    if not file or file.parse_status == ParseStatus.completed:
        return None
    key = f"{file.batch_id or 'single'}:{file.id}:{stage.value}"
    run = db.query(ParseStageRun).filter(ParseStageRun.idempotency_key == key).one_or_none()
    if run and run.status == "completed":
        return None
    if not run:
        run = ParseStageRun(file_id=file.id, stage=stage.value, idempotency_key=key, status="running", attempts=1)
        db.add(run)
    else:
        run.status = "running"
        run.attempts += 1
        run.error = None
    file.parse_status = ParseStatus.processing
    file.parse_stage = stage
    file.parse_error = None
    file.progress = STAGE_PROGRESS[stage]
    db.commit()
    return file


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finish_stage(db: Session, file: ProjectFile, next_stage: ParseStage, progress: int) -> None:
    current = db.query(ParseStageRun).filter(ParseStageRun.file_id == file.id, ParseStageRun.stage == file.parse_stage.value).one_or_none()
    if current:
        current.status = "completed"
        current.completed_at = datetime.now(timezone.utc)
    file.parse_stage = next_stage
    file.progress = progress
    db.commit()


def _complete_stage(db: Session, file_id: str, stage: ParseStage) -> None:
    run = db.query(ParseStageRun).filter(ParseStageRun.file_id == file_id, ParseStageRun.stage == stage.value).one_or_none()
    if run:
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)


def _fail_stage(db: Session, file_id: str, stage: ParseStage, exc: Exception, task) -> None:
    file = FileRepository(db).get(file_id)
    if not file:
        return
    error_message = str(exc).replace("\x00", "")
    run = db.query(ParseStageRun).filter(ParseStageRun.file_id == file.id, ParseStageRun.stage == stage.value).one_or_none()
    if run:
        run.status = "failed"
        run.error = error_message
    retries = getattr(getattr(task, "request", None), "retries", settings.max_parse_retries)
    retrying = isinstance(exc, RETRYABLE_ERRORS) and retries < settings.max_parse_retries
    file.parse_status = ParseStatus.processing if retrying else ParseStatus.failed
    file.parse_stage = stage
    file.parse_error = f"Retry scheduled: {error_message}" if retrying else error_message
    file.progress = 0 if not retrying else file.progress
    file.retry_count = (file.retry_count or 0) + 1
    if not retrying:
        dead_letter = db.query(ParseDeadLetter).filter(ParseDeadLetter.file_id == file.id).one_or_none()
        if dead_letter:
            dead_letter.attempts = file.retry_count
            dead_letter.error = error_message
        else:
            db.add(ParseDeadLetter(file_id=file.id, attempts=file.retry_count, error=error_message))
    db.commit()
    _refresh_batch(db, file.batch_id)


def _refresh_batch(db: Session, batch_id: str | None) -> None:
    if not batch_id:
        return
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
