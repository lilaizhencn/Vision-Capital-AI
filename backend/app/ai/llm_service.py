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

