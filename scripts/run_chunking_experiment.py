"""Индексация корпуса тремя стратегиями чанкинга в отдельные коллекции Qdrant.

Запуск:
    python -m scripts.run_chunking_experiment
"""

import asyncio
import logging
from pathlib import Path
import httpx

from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.core.schema import BaseNode
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import get_settings
from app.services.chunking import fixed_size, recursive, semantic

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

STRATEGIES = ["fixed", "recursive", "semantic"]
COLLECTION_MAP = {
    "fixed": "docs_fixed",
    "recursive": "docs_recursive",
    "semantic": "docs_semantic",
}


def upsert_nodes(client: QdrantClient, collection: str, nodes: list[BaseNode], dim: int) -> None:
    from qdrant_client.models import PointStruct
    import uuid

    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    points = []
    for node in nodes:
        if node.embedding is None:
            continue
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=node.embedding,
            payload={"text": node.text, "source": node.metadata.get("file_name", "")},
        ))

    for i in range(0, len(points), 256):
        batch = points[i:i + 256]
        client.upsert(collection_name=collection, points=batch, wait=True)


async def main() -> None:
    settings = get_settings()
    api_key = settings.llm.openai_api_key.get_secret_value()

    embed_model = OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=api_key,
        http_client=httpx.Client(trust_env=False),
        async_http_client=httpx.AsyncClient(trust_env=False),
    )
    Settings.embed_model = embed_model

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key, trust_env=False)

    documents = SimpleDirectoryReader(
        input_dir=str(settings.rag_data_dir), recursive=True
    ).load_data()
    logger.info("Загружено документов: %d", len(documents))

    for strategy in STRATEGIES:
        collection = COLLECTION_MAP[strategy]
        logger.info("=== Стратегия: %s → коллекция %s ===", strategy, collection)

        if strategy == "fixed":
            nodes = fixed_size(documents)
        elif strategy == "recursive":
            nodes = recursive(documents)
        else:
            nodes = semantic(documents, embed_model)

        # эмбеддинг нод (semantic уже считает при сплите, fixed/recursive — нет)
        if strategy != "semantic":
            texts = [n.text for n in nodes]
            batch_size = 100
            embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                resp = await embed_model.aget_text_embedding_batch(batch)
                embeddings.extend(resp)
            for node, emb in zip(nodes, embeddings):
                node.embedding = emb

        avg_len = sum(len(n.text) for n in nodes) / len(nodes) if nodes else 0
        logger.info("Чанков: %d | Средняя длина: %.0f символов", len(nodes), avg_len)

        upsert_nodes(client, collection, nodes, settings.embedding_dim)
        logger.info("Проиндексировано в %s", collection)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())