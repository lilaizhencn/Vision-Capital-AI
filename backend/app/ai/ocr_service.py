from __future__ import annotations

import base64
from io import BytesIO
import logging

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """OCR adapter with a vision-model path and a local Tesseract fallback."""

    def __init__(self) -> None:
        self.client = None
        if settings.llm_api_key:
            self.client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    def extract(self, data: bytes, content_type: str) -> str:
        if self.client:
            try:
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
            except Exception as exc:
                logger.warning("Vision OCR failed; falling back to local Tesseract OCR: %s", exc)
        return self._extract_local(data)

    @staticmethod
    def _extract_local(data: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("OCR requires a vision model or the local Tesseract dependencies") from exc
        try:
            with Image.open(BytesIO(data)) as image:
                return pytesseract.image_to_string(image, config="--psm 6").strip()
        except Exception as exc:
            raise RuntimeError("Local Tesseract OCR failed") from exc
