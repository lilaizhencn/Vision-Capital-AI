from __future__ import annotations

import base64

from openai import OpenAI

from app.core.config import settings


class OCRService:
    """OCR adapter using any OpenAI-compatible vision model."""

    def __init__(self) -> None:
        self.client = None
        if settings.llm_api_key:
            self.client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    def extract(self, data: bytes, content_type: str) -> str:
        if not self.client:
            raise RuntimeError("LLM_API_KEY is required for image and scanned-document OCR")
        encoded = base64.b64encode(data).decode("ascii")
        response = self.client.chat.completions.create(
            model=settings.ocr_model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Extract all readable text from the image. Preserve tables and line breaks. Return only extracted text."},
                {"role": "user", "content": [
                    {"type": "text", "text": "OCR this document accurately."},
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{encoded}"}},
                ]},
            ],
        )
        return response.choices[0].message.content or ""
