from io import BytesIO

import pandas as pd
from docx import Document
from pypdf import PdfReader

from app.ai.ocr_service import OCRService
from app.core.config import settings


class DocumentParserService:
    def __init__(self, ocr_service: OCRService | None = None) -> None:
        self.ocr_service = ocr_service or OCRService()

    def parse(self, filename: str, content_type: str, data: bytes) -> str:
        suffix = filename.lower().split(".")[-1]
        if suffix == "pdf":
            return self._parse_pdf(data)
        if suffix in {"doc", "docx"}:
            return self._parse_docx(data)
        if suffix in {"xls", "xlsx"}:
            return self._parse_excel(data)
        if suffix == "csv":
            return self._parse_csv(data)
        if suffix in {"txt", "md"}:
            return data.decode("utf-8", errors="ignore")
        if suffix in {"png", "jpg", "jpeg", "webp"}:
            return self.ocr_service.extract(data, content_type or f"image/{suffix}")
        raise ValueError(f"Unsupported file type: {suffix}")

    def _parse_pdf(self, data: bytes) -> str:
        reader = PdfReader(BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if text:
            return text
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to OCR scanned PDF pages") from exc
        document = fitz.open(stream=data, filetype="pdf")
        if len(document) > settings.ocr_max_pages:
            raise ValueError(f"Scanned PDF exceeds OCR page limit of {settings.ocr_max_pages}")
        pages: list[str] = []
        for page in document:
            image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")
            pages.append(self.ocr_service.extract(image, "image/png"))
        return "\n\n".join(pages).strip()

    def _parse_docx(self, data: bytes) -> str:
        document = Document(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    def _parse_excel(self, data: bytes) -> str:
        workbook = pd.read_excel(BytesIO(data), sheet_name=None)
        sections: list[str] = []
        for sheet_name, frame in workbook.items():
            sections.append(f"Sheet: {sheet_name}")
            sections.append(frame.fillna("").to_csv(index=False))
        return "\n".join(sections)

    def _parse_csv(self, data: bytes) -> str:
        frame = pd.read_csv(BytesIO(data))
        return frame.fillna("").to_csv(index=False)
