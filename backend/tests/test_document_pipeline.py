from io import BytesIO
import hashlib
import socket

import pandas as pd
import pytest
import fitz
from PIL import Image
from types import SimpleNamespace
from docx import Document
from app.ai.llm_service import LLMService
from app.ai.embedding_service import EmbeddingService
from app.services.rag_service import RAGService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.rag.chunking import chunk_text, estimate_tokens
from app.services.document_parser_service import DocumentParserService
from app.main import app
from app.core.database import Base, get_db
from app.storage.storage_service import LocalStorageService
from app.core.config import Settings, settings
from app.workers import tasks
from app.services import file_service
from app.api import websocket as websocket_api
from app.services.file_service import FileService
from app.services.file_validation_service import validate_file_signature
from app.services.virus_scan_service import VirusScanner


class FakeOCR:
    def extract(self, data: bytes, content_type: str) -> str:
        assert data
        assert content_type.startswith("image/")
        return "OCR result"


def test_parser_extracts_docx_text() -> None:
    document = Document()
    document.add_paragraph("Investment thesis")
    stream = BytesIO()
    document.save(stream)

    result = DocumentParserService().parse("memo.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", stream.getvalue())

    assert "Investment thesis" in result


def test_parser_extracts_docx_tables() -> None:
    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Revenue"
    table.cell(1, 1).text = "100"
    stream = BytesIO()
    document.save(stream)

    result = DocumentParserService().parse("table.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", stream.getvalue())

    assert "Table 1:" in result
    assert "Revenue | 100" in result


def test_llm_extraction_parses_json(monkeypatch) -> None:
    service = LLMService()
    monkeypatch.setattr(service, "generate", lambda _prompt: "```json\n{\"risks\": [\"liquidity\"]}\n```")

    assert service.extract_document_data("document") == {"risks": ["liquidity"]}


def test_parser_extracts_excel_sheets() -> None:
    stream = BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        pd.DataFrame({"metric": ["revenue"], "value": [100]}).to_excel(writer, index=False, sheet_name="Metrics")

    result = DocumentParserService().parse("metrics.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", stream.getvalue())

    assert "Sheet: Metrics" in result
    assert "revenue" in result


def test_parser_extracts_pdf_tables() -> None:
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    for y in (20, 60, 100):
        page.draw_line(fitz.Point(20, y), fitz.Point(260, y), color=(0, 0, 0), width=1)
    for x in (20, 140, 260):
        page.draw_line(fitz.Point(x, 20), fitz.Point(x, 100), color=(0, 0, 0), width=1)
    page.insert_text((30, 45), "Metric")
    page.insert_text((150, 45), "Value")
    page.insert_text((30, 85), "Revenue")
    page.insert_text((150, 85), "100")

    result = DocumentParserService().parse("table.pdf", "application/pdf", document.tobytes())

    assert "PDF Table 1.1:" in result
    assert "Revenue | 100" in result


def test_parser_delegates_images_to_ocr() -> None:
    result = DocumentParserService(ocr_service=FakeOCR()).parse("scan.png", "image/png", b"image-bytes")

    assert result == "OCR result"


@pytest.mark.parametrize(
    ("filename", "content_type", "image_format"),
    [("scan.jpg", "image/jpeg", "JPEG"), ("scan.webp", "image/webp", "WEBP")],
)
def test_parser_delegates_jpeg_and_webp_to_ocr(filename: str, content_type: str, image_format: str) -> None:
    stream = BytesIO()
    Image.new("RGB", (32, 32), "white").save(stream, format=image_format)

    result = DocumentParserService(ocr_service=FakeOCR()).parse(filename, content_type, stream.getvalue())

    assert result == "OCR result"


def test_scanned_pdf_uses_ocr_when_no_text_layer() -> None:
    document = fitz.open()
    document.new_page(width=100, height=100)

    result = DocumentParserService(ocr_service=FakeOCR()).parse("scan.pdf", "application/pdf", document.tobytes())

    assert result == "OCR result"


def test_ocr_falls_back_to_local_tesseract_when_vision_provider_fails(monkeypatch) -> None:
    from app.ai.ocr_service import OCRService

    service = OCRService()
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: (_ for _ in ()).throw(ValueError("vision unsupported")))))
    monkeypatch.setattr(service, "_extract_local", lambda _data: "local OCR result")

    assert service.extract(b"image-bytes", "image/png") == "local OCR result"


def test_file_validation_rejects_unsupported_extensions() -> None:
    with pytest.raises(Exception):
        FileService._validate_filename("payload.exe")

    with pytest.raises(Exception):
        FileService._validate_filename("no-extension")


def test_file_signature_validation_rejects_extension_spoofing() -> None:
    with pytest.raises(ValueError, match="signature"):
        validate_file_signature("fake.pdf", b"not a pdf")
    validate_file_signature("notes.txt", b"plain text")


def test_virus_scanner_is_explicitly_skipped_only_outside_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "virus_scan_enabled", False)
    assert VirusScanner().scan_bytes(b"safe") == "skipped"


def test_production_configuration_requires_llm_credentials() -> None:
    production = Settings(
        app_env="production",
        app_secret_key="app-secret",
        jwt_secret_key="jwt-secret",
        database_url="postgresql+psycopg://user:password@db/vision",
        r2_endpoint_url="https://example.r2.cloudflarestorage.com",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="app-public",
        virus_scan_enabled=True,
    )

    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        production.validate_production()

    production.llm_api_key = "test-key"
    production.validate_production()


def test_virus_scanner_streams_clamav_protocol(monkeypatch) -> None:
    class FakeConnection:
        def __init__(self):
            self.payload = bytearray()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def sendall(self, value):
            self.payload.extend(value)

        def recv(self, _size):
            return b"stream: OK\x00"

    fake = FakeConnection()
    monkeypatch.setattr(settings, "virus_scan_enabled", True)
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: fake)
    assert VirusScanner().scan_bytes(b"safe") == "stream: OK"
    assert bytes(fake.payload).startswith(b"zINSTREAM\x00")


def test_chunking_overlaps_and_estimates_tokens() -> None:
    text = "0123456789" * 300

    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    assert chunks[0][-20:] == chunks[1][:20]
    assert estimate_tokens(text) > 0


def test_parse_progress_matches_solution_stage_weights() -> None:
    assert [tasks.STAGE_PROGRESS[stage] for stage in tasks.STAGE_PROGRESS] == [10, 20, 60, 80, 95]


def test_local_storage_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "local_storage_path", tmp_path)
    storage = LocalStorageService()

    storage.upload_file("batch/file.txt", b"hello", "text/plain")

    assert storage.object_exists("batch/file.txt", expected_size=5)
    assert storage.download_file("batch/file.txt") == b"hello"
    destination = tmp_path / "streamed" / "file.txt"
    storage.download_file_to_path("batch/file.txt", destination)
    assert destination.read_bytes() == b"hello"


def test_health_contract_without_infrastructure() -> None:
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 503


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(tasks, "SessionLocal", TestSession)
    monkeypatch.setattr(websocket_api, "SessionLocal", TestSession)
    monkeypatch.setattr(settings, "local_storage_path", tmp_path)
    monkeypatch.setattr(settings, "celery_task_always_eager", True)
    eager_parse = lambda file_id: tasks.parse_uploaded_file_task.run(file_id)
    monkeypatch.setattr(file_service, "parse_uploaded_file_task", SimpleNamespace(delay=eager_parse))
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_auth_project_upload_and_parse_flow(api_client) -> None:
    registered = api_client.post("/api/auth/register", json={"email": "qa@example.com", "username": "qa", "password": "strong-password"})
    assert registered.status_code == 200
    token = registered.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    logged_in = api_client.post("/api/auth/login", json={"email": "qa@example.com", "password": "strong-password"})
    assert logged_in.status_code == 200
    assert api_client.get("/api/auth/me", headers=headers).json()["username"] == "qa"

    project = api_client.post("/api/projects", headers=headers, json={"name": "QA", "company_name": "Acme", "industry": "SaaS", "stage": "Seed"})
    assert project.status_code == 200
    project_id = project.json()["id"]

    uploaded = api_client.post(
        f"/api/projects/{project_id}/files/upload",
        headers=headers,
        files={"upload_file": ("memo.txt", b"Revenue grew 20 percent", "text/plain")},
    )
    assert uploaded.status_code == 200

    listed = api_client.get(f"/api/projects/{project_id}/files", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["filename"] == "memo.txt"
    assert listed.json()[0]["parse_status"] == "completed"
    assert listed.json()[0]["progress"] == 100


def test_single_upload_enforces_maximum_size(api_client, monkeypatch) -> None:
    token = api_client.post("/api/auth/register", json={"email": "size@example.com", "username": "size", "password": "strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post("/api/projects", headers=headers, json={"name": "Size QA", "company_name": "Acme", "industry": "SaaS", "stage": "Seed"}).json()["id"]
    monkeypatch.setattr(settings, "max_upload_size_bytes", 3)

    response = api_client.post(
        f"/api/projects/{project_id}/files/upload",
        headers=headers,
        files={"upload_file": ("memo.txt", b"four", "text/plain")},
    )

    assert response.status_code == 413


def test_batch_upload_complete_and_parse_flow(api_client) -> None:
    token = api_client.post("/api/auth/register", json={"email": "batch@example.com", "username": "batch", "password": "strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post("/api/projects", headers=headers, json={"name": "Batch QA", "company_name": "Acme", "industry": "SaaS", "stage": "Seed"}).json()["id"]

    created = api_client.post(f"/api/projects/{project_id}/file-batches", headers=headers, json={"files": [{"filename": "batch.txt", "size": 5, "content_type": "text/plain", "checksum_sha256": hashlib.sha256(b"hello").hexdigest()}]})
    assert created.status_code == 200
    batch = created.json()
    file_id = batch["files"][0]["id"]
    resumable = api_client.get(f"/api/file-batches/{batch['id']}", headers=headers)
    assert resumable.status_code == 200
    assert resumable.json()["upload_sessions"][0]["file_id"] == file_id

    uploaded = api_client.post(f"/api/file-batches/{batch['id']}/files/{file_id}/content", headers=headers, files={"upload_file": ("batch.txt", b"hello", "text/plain")})
    assert uploaded.status_code == 200
    completed = api_client.post(f"/api/file-batches/{batch['id']}/complete", headers=headers)
    assert completed.status_code == 200

    with api_client.websocket_connect(f"/api/ws/batches/{batch['id']}?token={token}") as websocket:
        progress = websocket.receive_json()
        assert progress["batch_id"] == batch["id"]
        assert progress["status"] == "completed"

    files = api_client.get(f"/api/projects/{project_id}/files", headers=headers).json()
    assert files[0]["parse_status"] == "completed"
    assert files[0]["batch_id"] == batch["id"]
    assert files[0]["checksum_sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert files[0]["virus_scan_status"] == "skipped"
    repeated = api_client.post(f"/api/file-batches/{batch['id']}/complete", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "completed"


def test_batch_checksum_mismatch_fails_parse(api_client) -> None:
    token = api_client.post("/api/auth/register", json={"email": "checksum@example.com", "username": "checksum", "password": "strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post(f"/api/projects", headers=headers, json={"name": "Checksum QA", "company_name": "Acme", "industry": "SaaS", "stage": "Seed"}).json()["id"]
    created = api_client.post(
        f"/api/projects/{project_id}/file-batches",
        headers=headers,
        json={"files": [{"filename": "checksum.txt", "size": 5, "content_type": "text/plain", "checksum_sha256": "0" * 64}]},
    ).json()
    file_id = created["files"][0]["id"]
    api_client.post(f"/api/file-batches/{created['id']}/files/{file_id}/content", headers=headers, files={"upload_file": ("checksum.txt", b"hello", "text/plain")})
    with pytest.raises(ValueError, match="checksum"):
        api_client.post(f"/api/file-batches/{created['id']}/complete", headers=headers)
    file_item = api_client.get(f"/api/projects/{project_id}/files", headers=headers).json()[0]
    assert file_item["parse_status"] == "failed"
    assert "checksum" in file_item["parse_error"].lower()


def test_project_dashboard_chat_and_report_flow(api_client, monkeypatch) -> None:
    monkeypatch.setattr(RAGService, "similarity_search", lambda _self, *_args, **_kwargs: [])
    monkeypatch.setattr(LLMService, "generate", lambda _self, _prompt: "stub AI response")
    token = api_client.post("/api/auth/register", json={"email": "business@example.com", "username": "business", "password": "strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = api_client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Business QA", "company_name": "Acme", "industry": "SaaS", "stage": "Seed"},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]

    updated = api_client.put(
        f"/api/projects/{project_id}",
        headers=headers,
        json={"name": "Business QA Updated", "company_name": "Acme", "industry": "SaaS", "stage": "Series A", "description": "Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["stage"] == "Series A"
    assert api_client.get("/api/projects", headers=headers).json()[0]["name"] == "Business QA Updated"

    dashboard = api_client.get("/api/dashboard/summary", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_projects"] == 1

    chat = api_client.post(f"/api/projects/{project_id}/chat", headers=headers, json={"message": "Summarize the project"})
    assert chat.status_code == 200
    assert chat.json() == {"answer": "stub AI response", "citations": []}

    generated = api_client.post(f"/api/projects/{project_id}/reports/generate", headers=headers)
    assert generated.status_code == 200
    assert generated.json()["content"] == "stub AI response"
    listed_reports = api_client.get(f"/api/projects/{project_id}/reports", headers=headers)
    assert listed_reports.status_code == 200
    assert len(listed_reports.json()) == 1
    recent_reports = api_client.get("/api/reports", headers=headers)
    assert recent_reports.status_code == 200
    assert len(recent_reports.json()) == 1

    other_token = api_client.post(
        "/api/auth/register",
        json={"email": "other-business@example.com", "username": "other-business", "password": "strong-password"},
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    assert api_client.get("/api/reports", headers=other_headers).json() == []
    assert api_client.get(f"/api/projects/{project_id}/reports", headers=other_headers).status_code == 404

    assert api_client.delete(f"/api/projects/{project_id}", headers=headers).status_code == 200
    assert api_client.get(f"/api/projects/{project_id}", headers=headers).status_code == 404


def test_monitoring_updates_are_persisted_and_owner_scoped(api_client) -> None:
    token = api_client.post("/api/auth/register", json={"email": "monitor@example.com", "username": "monitor", "password": "strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Monitor QA", "company_name": "Acme", "industry": "SaaS", "stage": "Series A"},
    ).json()["id"]

    created = api_client.post(
        f"/api/projects/{project_id}/monitoring",
        headers=headers,
        json={"metric_name": "月度收入", "metric_value": "320", "metric_unit": "万元", "risk_level": "watch", "note": "客户集中度需要继续跟踪"},
    )
    assert created.status_code == 200
    assert created.json()["risk_level"] == "watch"
    listed = api_client.get(f"/api/projects/{project_id}/monitoring", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["metric_name"] == "月度收入"

    other_token = api_client.post("/api/auth/register", json={"email": "other-monitor@example.com", "username": "other-monitor", "password": "strong-password"}).json()["access_token"]
    assert api_client.get(f"/api/projects/{project_id}/monitoring", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404


def test_chat_falls_back_to_recent_chunks_when_embeddings_are_unavailable(api_client, monkeypatch) -> None:
    monkeypatch.setattr(EmbeddingService, "embed_text", lambda _self, _text: (_ for _ in ()).throw(RuntimeError("embedding unavailable")))
    monkeypatch.setattr(LLMService, "generate", lambda _self, _prompt: "fallback response")
    token = api_client.post("/api/auth/register", json={"email": "rag@example.com", "username": "rag", "password": "strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post(
        "/api/projects",
        headers=headers,
        json={"name": "RAG QA", "company_name": "Acme", "industry": "SaaS", "stage": "Seed"},
    ).json()["id"]
    uploaded = api_client.post(
        f"/api/projects/{project_id}/files/upload",
        headers=headers,
        files={"upload_file": ("notes.txt", b"Revenue grew 20 percent", "text/plain")},
    )
    assert uploaded.status_code == 200

    response = api_client.post(f"/api/projects/{project_id}/chat", headers=headers, json={"message": "What grew?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "fallback response"
    assert response.json()["citations"][0]["filename"] == "notes.txt"


def test_persist_stage_tolerates_embedding_provider_errors(api_client, monkeypatch) -> None:
    monkeypatch.setattr(EmbeddingService, "embed_text", lambda _self, _text: (_ for _ in ()).throw(ValueError("embedding endpoint returned 404")))
    token = api_client.post("/api/auth/register", json={"email": "embedding-qa@example.com", "username": "embeddingqa", "password": "strong-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post("/api/projects", headers=headers, json={"name": "Embedding QA", "company_name": "Acme", "industry": "SaaS", "stage": "Seed"}).json()["id"]

    uploaded = api_client.post(
        f"/api/projects/{project_id}/files/upload",
        headers=headers,
        files={"upload_file": ("notes.txt", b"Revenue grew 20 percent", "text/plain")},
    )

    assert uploaded.status_code == 200
    file_item = api_client.get(f"/api/projects/{project_id}/files", headers=headers).json()[0]
    assert file_item["parse_status"] == "completed"
    assert file_item["progress"] == 100


def test_llm_service_uses_openai_compatible_chat_completions(monkeypatch) -> None:
    service = LLMService()
    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))])

    service.client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    assert service.generate("test prompt") == "answer"
    assert calls["messages"] == [{"role": "user", "content": "test prompt"}]
