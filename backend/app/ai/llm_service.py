import json

from openai import OpenAI

from app.core.config import settings


class LLMService:
    def __init__(self) -> None:
        self.client = None
        if settings.llm_api_key:
            self.client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    def generate(self, prompt: str) -> str:
        if not self.client:
            raise RuntimeError("LLM_API_KEY is not configured, LLM service is unavailable.")
        response = self.client.responses.create(
            model=settings.llm_model,
            input=prompt,
        )
        return response.output_text

    def extract_document_data(self, text: str) -> dict:
        """Extract stable investment fields and preserve malformed model output for review."""
        prompt = f"""
Extract investment research data from the document below.
Return JSON only with these keys: company, industry, stage, revenue, financial_metrics,
investment_highlights, risks, due_diligence_questions, source_notes.
Use null or [] when the document does not contain a value. Do not invent facts.

DOCUMENT:
{text[:24000]}
""".strip()
        raw = self.generate(prompt).strip()
        cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw": raw}
        return value if isinstance(value, dict) else {"raw": raw}
