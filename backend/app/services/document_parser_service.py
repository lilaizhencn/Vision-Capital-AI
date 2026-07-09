from io import BytesIO

import pandas as pd
from docx import Document
from pypdf import PdfReader


class DocumentParserService:
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
            return "OCR 占位：当前版本暂未接入图片 OCR，可在后续版本接入 OCR 服务。"
        raise ValueError(f"Unsupported file type: {suffix}")

    def _parse_pdf(self, data: bytes) -> str:
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

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

