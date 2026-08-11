"""RAG на LlamaIndex.

Запуск отдельно:
    python -m app.services.rag
"""

import logging

from llama_index.core import (
    PromptTemplate,
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient

from app.core.config import Settings as AppSettings
from app.core.config import get_settings

logger = logging.getLogger(__name__)

QA_PROMPT = PromptTemplate(
    "Ниже приведён контекст из базы знаний.\n"
    "---------------------\n{context_str}\n---------------------\n"
    "Ответь на вопрос, опираясь ТОЛЬКО на контекст. Если ответа в контексте нет — "
    "честно напиши, что не нашёл ответа в базе знаний, и ничего не выдумывай. "
    "Отвечай по-русски, коротко и по делу.\n"
    "Вопрос: {query_str}\n"
    "Ответ: "
)


def format_result(response, threshold: float) -> dict:
    nodes = response.source_nodes
    top_score = max((node.score or 0.0 for node in nodes), default=0.0)
    if top_score < threshold:
        answer_text = "В базе знаний нет ответа на этот вопрос."
    else:
        answer_text = str(response)
    return {
        "answer": answer_text,
        "top_score": round(top_score, 3),
        "sources": [
            {
                "text": node.text[:300],
                "source": node.metadata.get("file_name"),
                "score": round(node.score or 0.0, 3),
            }
            for node in nodes
        ],
    }


class RAGService:

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        api_key = settings.llm.openai_api_key.get_secret_value()
        qdrant_key = (
            settings.qdrant_api_key
        )

        Settings.llm = OpenAI(model=settings.rag_llm_model, temperature=0.0, api_key=api_key)
        Settings.embed_model = OpenAIEmbedding(model=settings.embedding_model, api_key=api_key)
        Settings.node_parser = SentenceSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )

        self._client = QdrantClient(url=settings.qdrant_url, api_key=qdrant_key, trust_env=False)
        self._aclient = AsyncQdrantClient(url=settings.qdrant_url, api_key=qdrant_key, trust_env=False)
        self._index: VectorStoreIndex | None = None
        self._engine = None

    def _vector_store(self) -> QdrantVectorStore:
        return QdrantVectorStore(
            collection_name=self._settings.rag_collection,
            client=self._client,
            aclient=self._aclient,
        )

    def _collection_ready(self) -> bool:
        if not self._client.collection_exists(self._settings.rag_collection):
            return False
        return self._client.count(self._settings.rag_collection).count > 0

    def build(self) -> None:
        vector_store = self._vector_store()
        if self._collection_ready():
            self._index = VectorStoreIndex.from_vector_store(vector_store)
            logger.info(
                "RAG: подключён к коллекции %s (%d точек)",
                self._settings.rag_collection,
                self._client.count(self._settings.rag_collection).count,
            )
        else:
            documents = SimpleDirectoryReader(
                input_dir=str(self._settings.rag_data_dir),
                recursive=True,
            ).load_data()
            storage = StorageContext.from_defaults(vector_store=vector_store)
            self._index = VectorStoreIndex.from_documents(documents, storage_context=storage)
            logger.info(
                "RAG: проиндексировано %d документов в коллекцию %s",
                len(documents),
                self._settings.rag_collection,
            )

        self._engine = self._index.as_query_engine(
            similarity_top_k=self._settings.rag_top_k,
            text_qa_template=QA_PROMPT,
        )

    async def answer(self, question: str) -> dict:
        if self._engine is None:
            raise RuntimeError("RAG-индекс не инициализирован: сначала вызвать build().")
        response = await self._engine.aquery(question)
        return format_result(response, self._settings.rag_score_threshold)

    async def close(self) -> None:
        try:
            await self._aclient.close()
        except Exception:
            logger.debug("ошибка при закрытии async Qdrant-клиента", exc_info=True)
        try:
            self._client.close()
        except Exception:
            logger.debug("ошибка при закрытии Qdrant-клиента", exc_info=True)


def _demo() -> None:
    import asyncio
    import json

    async def run() -> None:
        service = RAGService(get_settings())
        service.build()
        for question in (
            "Каков порядок расторжения договора аренды?",
            "Как приготовить борщ?",
        ):
            result = await service.answer(question)
            print(f"\nВопрос: {question}")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        await service.close()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    _demo()
    
