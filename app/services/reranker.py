from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.schema import NodeWithScore


class Reranker:
    def __init__(self, top_n: int = 5, model: str = "BAAI/bge-reranker-v2-m3") -> None:
        self._reranker = SentenceTransformerRerank(model=model, top_n=top_n)

    def rerank(self, query: str, nodes: list[NodeWithScore]) -> list[NodeWithScore]:
        return self._reranker.postprocess_nodes(nodes, query_str=query)