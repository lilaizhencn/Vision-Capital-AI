from io import BytesIO

import pandas as pd
import pytest
from types import SimpleNamespace
from docx import Document
from app.ai.llm_service import LLMService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.rag.chunking import chunk_text, estimate_tokens
from app.services.document_parser_service import DocumentParserService
from app.main import app
from app.core.database import Base, get_db
from app.storage.storage_service import LocalStorageService
from app.core.config import settings
from app.workers import tasks
from app.services import file_service
from app.api import websocket as websocket_api
from app.services.file_service import FileService


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


def test_parser_delegates_images_to_ocr() -> None:
    result = DocumentParserService(ocr_service=FakeOCR()).parse("scan.png", "image/png", b"image-bytes")

    assert result == "OCR result"


def test_file_validation_rejects_unsupported_extensions() -> None:
    with pytest.raises(Exception):
        FileService._validate_filename("payload.exe")

    with pytest.raises(Exception):
        FileService._validate_filename("no-extension")


def test_chunking_overlaps_and_estimates_tokens() -> None:
    text = "0123456789" * 300

    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    assert chunks[0][-20:] == chunks[1][:20]
    assert estimate_tokens(text) > 0


def test_local_storage_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "local_storage_path", tmp_path)
    storage = LocalStorageService()

    storage.upload_file("batch/file.txt", b"hello", "text/plain")

    assert storage.object_exists("batch/file.txt", expected_size=5)
    assert storage.download_file("batch/file.txt") == b"hello"


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

    created = api_client.post(f"/api/projects/{project_id}/file-batches", headers=headers, json={"files": [{"filename": "batch.txt", "size": 5, "content_type": "text/plain"}]})
    assert created.status_code == 200
    batch = created.json()
    file_id = batch["files"][0]["id"]

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
    repeated = api_client.post(f"/api/file-batches/{batch['id']}/complete", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "completed"
