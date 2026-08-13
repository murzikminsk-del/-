"""Сравнение метрик retrieval до и после re-ranker.

Запуск:
    python -m scripts.run_reranker_eval
"""

import httpx
from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.embeddings.openai import OpenAIEmbedding
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.services.reranker import Reranker
from app.services.retrieval_eval import evaluate, load_dataset

COLLECTION = "docs_recursive"
DATASET_PATH = "tests/eval/retrieval_dataset.json"
TOP_K_RETRIEVE = 10
TOP_N_RERANK = 5


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

    def retrieve_with_scores(self, query: str, top_k: int) -> list[NodeWithScore]:
        vector = self._embed.get_text_embedding(query)
        results = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=top_k,
        ).points
        return [
            NodeWithScore(
                node=TextNode(
                    text=p.payload.get("text", ""),
                    metadata={"file_name": p.payload.get("source", "")},
                ),
                score=p.score,
            )
            for p in results
        ]


class RerankedRetriever:
    def __init__(self, base: QdrantRetriever, reranker: Reranker, top_k_retrieve: int) -> None:
        self._base = base
        self._reranker = reranker
        self._top_k_retrieve = top_k_retrieve

    def retrieve(self, query: str, top_k: int) -> list[str]:
        nodes = self._base.retrieve_with_scores(query, self._top_k_retrieve)
        reranked = self._reranker.rerank(query, nodes)
        return [n.node.metadata.get("file_name", "") for n in reranked[:top_k]]


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

    base_retriever = QdrantRetriever(client, COLLECTION, embed_model)
    reranker = Reranker(top_n=TOP_N_RERANK)
    reranked_retriever = RerankedRetriever(base_retriever, reranker, TOP_K_RETRIEVE)

    print(f"\n{'Режим':<20} {'Hit@5':>7} {'MRR@5':>7} {'Recall@5':>9}")
    print("-" * 47)

    m_base = evaluate(dataset, base_retriever, k=TOP_N_RERANK)
    print(f"{'без re-ranker':<20} {m_base['hit_rate']:>7.4f} {m_base['mrr']:>7.4f} {m_base['recall']:>9.4f}")

    m_reranked = evaluate(dataset, reranked_retriever, k=TOP_N_RERANK)
    print(f"{'с re-ranker':<20} {m_reranked['hit_rate']:>7.4f} {m_reranked['mrr']:>7.4f} {m_reranked['recall']:>9.4f}")

    client.close()


if __name__ == "__main__":
    main()