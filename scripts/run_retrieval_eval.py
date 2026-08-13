"""Оценка трёх стратегий чанкинга по метрикам ретривала.

Запуск (после run_chunking_experiment.py):
    python -m scripts.run_retrieval_eval
"""
import httpx
from qdrant_client import QdrantClient
from llama_index.embeddings.openai import OpenAIEmbedding

from app.core.config import get_settings
from app.services.retrieval_eval import evaluate, load_dataset

COLLECTIONS = {
    "fixed_size":  "docs_fixed",
    "recursive":   "docs_recursive",
    "semantic":    "docs_semantic",
}
DATASET_PATH = "tests/eval/retrieval_dataset.json"
TOP_K = 5


class QdrantRetriever:
    def __init__(self, client: QdrantClient, collection: str, embed_model: OpenAIEmbedding) -> None:
        self._client = client
        self._collection = collection
        self._embed = embed_model

    def retrieve(self, query: str, top_k: int) -> list[str]:
        vector = self._embed.get_text_embedding(query)
        results = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=top_k,
        ).points
        return [p.payload.get("source", "") for p in results]


def main() -> None:
    settings = get_settings()
    api_key = settings.llm.openai_api_key.get_secret_value()

    embed_model = OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=api_key,
        http_client=httpx.Client(trust_env=False),
        async_http_client=httpx.AsyncClient(trust_env=False),
    )
    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key, trust_env=False)

    dataset = load_dataset(DATASET_PATH)

    print(f"\n{'Стратегия':<15} {'Hit@5':>7} {'MRR@5':>7} {'Recall@5':>9}")
    print("-" * 42)

    for name, collection in COLLECTIONS.items():
        retriever = QdrantRetriever(client, collection, embed_model)
        metrics = evaluate(dataset, retriever, k=TOP_K)
        print(f"{name:<15} {metrics['hit_rate']:>7.4f} {metrics['mrr']:>7.4f} {metrics['recall']:>9.4f}")

    client.close()


if __name__ == "__main__":
    main()