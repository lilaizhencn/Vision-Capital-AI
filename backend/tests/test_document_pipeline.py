from io import BytesIO

import pandas as pd
from docx import Document

from app.rag.chunking import chunk_text, estimate_tokens
from app.services.document_parser_service import DocumentParserService


def test_parser_extracts_docx_text() -> None:
    document = Document()
    document.add_paragraph("Investment thesis")
    stream = BytesIO()
    document.save(stream)

    result = DocumentParserService().parse("memo.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", stream.getvalue())

    assert "Investment thesis" in result


def test_parser_extracts_excel_sheets() -> None:
    stream = BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        pd.DataFrame({"metric": ["revenue"], "value": [100]}).to_excel(writer, index=False, sheet_name="Metrics")

    result = DocumentParserService().parse("metrics.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", stream.getvalue())

    assert "Sheet: Metrics" in result
    assert "revenue" in result


def test_chunking_overlaps_and_estimates_tokens() -> None:
    text = "0123456789" * 300

    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    assert chunks[0][-20:] == chunks[1][:20]
    assert estimate_tokens(text) > 0
