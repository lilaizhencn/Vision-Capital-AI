from openai import OpenAI

from app.core.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.client = None
        if settings.llm_api_key:
            self.client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    def embed_text(self, text: str) -> list[float]:
        if not self.client:
            raise RuntimeError("LLM_API_KEY is not configured, embedding service is unavailable.")
        response = self.client.embeddings.create(model=settings.embedding_model, input=text)
        return list(response.data[0].embedding)

