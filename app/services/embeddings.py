import hashlib
from pathlib import Path

import diskcache
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

_in_memory: dict[str, list[float]] = {}
_disk_cache = diskcache.Cache(Path(".embedding_cache"))

def _cache_key(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def _fetch_embeddings(client: AsyncOpenAI, texts: list[str], model: str) -> list[list[float]]:
    response = await client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

async def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    model = settings.embedding_model
    client = AsyncOpenAI(api_key=settings.llm.openai_api_key.get_secret_value())
      
    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []
    
    for i, text in enumerate(texts):
        key = _cache_key(text, model)
        if key in _in_memory:
            results[i] = _in_memory[key]
        elif key in _disk_cache:
            vec = _disk_cache[key]
            _in_memory[key] = vec
            results[i] = vec
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)
    
    for batch_start in range(0, len(uncached_texts), 100):
        batch = uncached_texts[batch_start : batch_start + 100]
        vectors = await _fetch_embeddings(client, batch, model)
        for j, vec in enumerate(vectors):
            idx = uncached_indices[batch_start + j]
            key = _cache_key(texts[idx], model)
            _in_memory[key] = vec
            _disk_cache[key] = vec
            results[idx] = vec
            
    return results  # type: ignore[return-value]