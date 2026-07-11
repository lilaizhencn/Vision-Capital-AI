import hashlib
import math

from openai import OpenAI

from app.core.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.client = None
        if settings.llm_api_key and not settings.embedding_model.startswith("local-hash-"):
            self.client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    def embed_text(self, text: str) -> list[float]:
        if settings.embedding_model.startswith("local-hash-"):
            return self._local_hash_embedding(text)
        if not self.client:
            raise RuntimeError("LLM_API_KEY is not configured, embedding service is unavailable.")
        response = self.client.embeddings.create(model=settings.embedding_model, input=text)
        return list(response.data[0].embedding)

    def _local_hash_embedding(self, text: str) -> list[float]:
        """Keep local deployments searchable when a chat-only provider has no embedding API."""
        dimensions = settings.embedding_dimension
        vector = [0.0] * dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
