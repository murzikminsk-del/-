"""Сравнение метрик cosine vs dot product на 5 запросах из предметной области."""

import asyncio

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import get_settings
from app.services.embeddings import embed_texts

QUERIES = [
    "Можно ли расторгнуть договор если контрагент систематически нарушает сроки оплаты?",
    "Кто несёт ответственность за сохранность оборудования после передачи заказчику?",
    "В какой момент исключительные права на разработанное ПО переходят заказчику?",
    "Что делать при наступлении обстоятельств непреодолимой силы?",
    "Каков порядок созыва общего собрания участников общества?",
]


async def main() -> None:
    settings = get_settings()
    main_client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=30.0,
        trust_env=False,
    )

    # Получаем все точки с векторами из основной коллекции
    print("Читаем точки из основной коллекции...")
    all_points: list[PointStruct] = []
    offset = None
    while True:
        result, offset = await main_client.scroll(
            collection_name=settings.qdrant_collection,
            limit=256,
            offset=offset,
            with_vectors=True,
            with_payload=True,
        )
        for p in result:
            all_points.append(PointStruct(id=p.id, vector=p.vector, payload=p.payload))
        if offset is None:
            break
    print(f"Получено {len(all_points)} точек")

    # Создаём две временные коллекции
    for name, distance in [("documents_cosine", Distance.COSINE), ("documents_dot", Distance.DOT)]:
        existing = {c.name for c in (await main_client.get_collections()).collections}
        if name not in existing:
            await main_client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=settings.embedding_dim, distance=distance),
            )
        # Заливаем точки батчами
        for i in range(0, len(all_points), 256):
            batch = all_points[i : i + 256]
            is_last = (i + 256) >= len(all_points)
            await main_client.upsert(collection_name=name, points=batch, wait=is_last)
        print(f"Коллекция {name} готова")

    # Эмбеддим запросы
    print("\nЭмбеддим запросы...")
    query_vectors = await embed_texts(QUERIES)

    # Сравниваем результаты
    print("\n" + "=" * 80)
    all_match = True
    rows = []
    for query, qvec in zip(QUERIES, query_vectors):
        cosine_res = await main_client.query_points(
            collection_name="documents_cosine", query=qvec, limit=5, with_payload=False
        )
        dot_res = await main_client.query_points(
            collection_name="documents_dot", query=qvec, limit=5, with_payload=False
        )
        cosine_ids = [str(p.id) for p in cosine_res.points]
        dot_ids = [str(p.id) for p in dot_res.points]
        match = cosine_ids == dot_ids
        if not match:
            all_match = False
        rows.append((query[:60], cosine_ids, dot_ids, match))
        print(f"Запрос: {query[:70]}")
        print(f"  cosine top-5: {cosine_ids}")
        print(f"  dot    top-5: {dot_ids}")
        print(f"  Совпало: {'ДА' if match else 'НЕТ'}")
        print()

    print("=" * 80)
    print(f"Итог: ранжирование совпадает во всех запросах = {all_match}")
    print("OpenAI text-embedding-3-small возвращает нормализованные векторы,")
    print("поэтому cosine similarity == dot product. Оставляем COSINE как стандарт.")

    # Удаляем временные коллекции
    await main_client.delete_collection("documents_cosine")
    await main_client.delete_collection("documents_dot")
    print("\nВременные коллекции удалены.")
    await main_client.close()


if __name__ == "__main__":
    asyncio.run(main())
