import asyncio
import json
import uuid
from pathlib import Path

from tqdm import tqdm
from qdrant_client.models import PointStruct

from app.core.config import get_settings
from app.services.embeddings import embed_texts
from app.services.vector_store import VectorStore


def make_id(source: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}:{chunk_index}"))


async def main() -> None:
    settings = get_settings()
    store = VectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection=settings.qdrant_collection,
        dim=settings.embedding_dim,
    )
    await store.ensure_collection()

    records = [
        json.loads(line)
        for line in Path("data/sample_kb.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    texts = [r["text"] for r in records]
    vectors = await embed_texts(texts)

    points = [
        PointStruct(
            id=make_id(r["source"], r["chunk_index"]),
            vector=vectors[i],
            payload={
                "source": r["source"],
                "text": r["text"],
                "category": r["category"],
                "created_at": r["created_at"],
                "chunk_index": r["chunk_index"],
            },
        )
        for i, r in enumerate(records)
    ]

    for i in tqdm(range(0, len(points), 256), desc="Загрузка в Qdrant"):
        batch = points[i : i + 256]
        is_last = (i + 256) >= len(points)
        await store.client.upsert(
            collection_name=store.collection,
            points=batch,
            wait=is_last,
        )

    count = await store.count()
    print(f"Точек в коллекции: {count}")
    await store.close()


if __name__ == "__main__":
    asyncio.run(main())
