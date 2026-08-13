"""Перебор гиперпараметров чанкинга (recursive стратегия).

Запуск:
    python -m scripts.run_hyperparam_search
"""

import httpx
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

from app.core.config import get_settings
from app.services.retrieval_eval import evaluate, load_dataset

DATASET_PATH = "tests/eval/retrieval_dataset.json"
COLLECTION = "hp_search_tmp"
TOP_K = 5

EXPERIMENTS = [
    {"chunk_size": 256, "chunk_overlap": 32},
    {"chunk_size": 256, "chunk_overlap": 64},
    {"chunk_size": 512, "chunk_overlap": 32},
    {"chunk_size": 512, "chunk_overlap": 64},
]


class QdrantRetriever:
    def __init__(self, client, collection, embed_model):
        self._client = client
        self._collection = collection
        self._embed = embed_model

    def retrieve(self, query: str, top_k: int) -> list[str]:
        vector = self._embed.get_text_embedding(query)
        results = self._client.query_points(
            collection_name=self._collection, query=vector, limit=top_k
        ).points
        return [p.payload.get("source", "") for p in results]


def index_nodes(client, collection, nodes, embed_model, dim):
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    texts = [n.text for n in nodes]
    embeddings = []
    for i in range(0, len(texts), 100):
        embeddings.extend(embed_model.get_text_embedding_batch(texts[i:i+100]))
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload={"text": n.text, "source": n.metadata.get("file_name", "")},
        )
        for n, emb in zip(nodes, embeddings)
    ]
    for i in range(0, len(points), 256):
        client.upsert(collection_name=collection, points=points[i:i+256], wait=True)


def main():
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
    dataset = load_dataset(DATASET_PATH)

    documents = SimpleDirectoryReader(
        input_dir=str(settings.rag_data_dir), recursive=True
    ).load_data()

    print(f"\n{'chunk_size':>12} {'overlap':>8} {'Hit@5':>7} {'MRR@5':>7} {'Recall@5':>9}")
    print("-" * 48)

    best = {"mrr": 0}
    for exp in EXPERIMENTS:
        splitter = SentenceSplitter(
            chunk_size=exp["chunk_size"],
            chunk_overlap=exp["chunk_overlap"],
            paragraph_separator="\n\n",
        )
        nodes = splitter.get_nodes_from_documents(documents)
        index_nodes(client, COLLECTION, nodes, embed_model, settings.embedding_dim)

        retriever = QdrantRetriever(client, COLLECTION, embed_model)
        m = evaluate(dataset, retriever, k=TOP_K)

        print(f"{exp['chunk_size']:>12} {exp['chunk_overlap']:>8} {m['hit_rate']:>7.4f} {m['mrr']:>7.4f} {m['recall']:>9.4f}")

        if m["mrr"] > best["mrr"]:
            best = {**exp, **m}

    client.delete_collection(COLLECTION)
    client.close()

    print(f"\nЛучшая конфигурация: chunk_size={best['chunk_size']}, overlap={best['chunk_overlap']}")
    print(f"  Hit@5={best['hit_rate']:.4f}, MRR@5={best['mrr']:.4f}, Recall@5={best['recall']:.4f}")


if __name__ == "__main__":
    main()