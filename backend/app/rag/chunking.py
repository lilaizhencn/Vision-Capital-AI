from app.core.config import settings


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = start + settings.chunk_size
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = max(end - settings.chunk_overlap, start + 1)
    return chunks

