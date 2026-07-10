from app.core.config import settings


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    size = chunk_size or settings.chunk_size
    overlap_size = overlap if overlap is not None else settings.chunk_overlap
    if size <= 0 or overlap_size < 0 or overlap_size >= size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = start + size
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = max(end - overlap_size, start + 1)
    return chunks
