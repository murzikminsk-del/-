import json
from pathlib import Path
from typing import Protocol


class Retriever(Protocol):
    def retrieve(self, query: str, top_k: int) -> list[str]:
        """Возвращает список file_name найденных чанков, от лучшего к худшему."""
        ...


def hit_rate_at_k(retrieved: list[str], relevant: list[str]) -> float:
    if not relevant:
        return 1.0  # out-of-domain вопрос — считаем нейтральным
    return float(any(r in retrieved for r in relevant))


def mrr_at_k(retrieved: list[str], relevant: list[str]) -> float:
    if not relevant:
        return 1.0
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1.0 / rank
    return 0.0


def recall_at_k(retrieved: list[str], relevant: list[str]) -> float:
    if not relevant:
        return 1.0
    hits = sum(1 for r in relevant if r in retrieved)
    return hits / len(relevant)


def evaluate(dataset: list[dict], retriever: "Retriever", k: int = 5) -> dict:
    hr_scores, mrr_scores, recall_scores = [], [], []

    for item in dataset:
        relevant = item["relevant_doc_ids"]
        retrieved = retriever.retrieve(item["question"], top_k=k)

        hr_scores.append(hit_rate_at_k(retrieved, relevant))
        mrr_scores.append(mrr_at_k(retrieved, relevant))
        recall_scores.append(recall_at_k(retrieved, relevant))

    return {
        "hit_rate": round(sum(hr_scores) / len(hr_scores), 4),
        "mrr": round(sum(mrr_scores) / len(mrr_scores), 4),
        "recall": round(sum(recall_scores) / len(recall_scores), 4),
        "n_queries": len(dataset),
    }


def load_dataset(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))