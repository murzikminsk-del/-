# Vector Store — документация

## Метрика

### Cosine vs Dot Product

Эксперимент проведён на коллекции `documents` (1308 точек, модель `text-embedding-3-small`, dim=1536).
Созданы две временные коллекции — `documents_cosine` и `documents_dot` — на одних и тех же векторах.
Для каждого из 5 запросов сравнён top-5.

| Запрос | Cosine top-5 (ID) | Dot top-5 (ID) | Совпало |
|--------|-------------------|----------------|---------|
| Можно ли расторгнуть договор если контрагент систематически нарушает сроки оплаты? | cc04d9b5, 69558cfc, ee418887, 513f30cd, 04e21028 | cc04d9b5, 69558cfc, ee418887, 513f30cd, 04e21028 | ДА |
| Кто несёт ответственность за сохранность оборудования после передачи заказчику? | 1d984822, 902217d4, 5e530e70, 73b8d0cf, 4081d731 | 1d984822, 902217d4, 5e530e70, 73b8d0cf, 4081d731 | ДА |
| В какой момент исключительные права на разработанное ПО переходят заказчику? | 801cbd82, 5eb5aa2e, 9ff7b9f9, edacbe4a, 81678ce4 | 801cbd82, 5eb5aa2e, 9ff7b9f9, edacbe4a, 81678ce4 | ДА |
| Что делать при наступлении обстоятельств непреодолимой силы? | 8ae6f2c9, 21e9e5f4, f40c1bbc, 4eafe160, f6f78788 | 8ae6f2c9, 21e9e5f4, f40c1bbc, 4eafe160, f6f78788 | ДА |
| Каков порядок созыва общего собрания участников общества? | 3ad831e3, accfc799, d2975d29, 8c49a57a, 0dfd7df8 | 3ad831e3, accfc799, d2975d29, 8c49a57a, 0dfd7df8 | ДА |

**Вывод:** ранжирование совпадает во всех 5 запросах.

**Почему оставляем COSINE в production:** `text-embedding-3-small` возвращает нормализованные векторы (||v|| = 1), поэтому cosine similarity и dot product дают математически идентичный результат. COSINE выбран как более универсальный стандарт — при замене модели на ненормализованную поведение останется корректным, тогда как dot product на ненормализованных векторах даёт некорректное ранжирование.

Параметры HNSW оставлены по умолчанию Qdrant: `m=16, ef_construct=100` — для корпуса в ~1300 документов эти значения обеспечивают recall >99% при latency <5 мс, избыточная настройка нецелесообразна.

---

## Фильтрация по metadata

### Фильтр 1 — Match по строке (category)

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

query_filter = Filter(
    must=[
        FieldCondition(key="category", match=MatchValue(value="legal"))
    ]
)
results = await store.search(query_vector=qvec, top_k=3, query_filter=query_filter)
```

**Запрос:** «Расторжение договора при нарушении сроков оплаты»

**Top-3 результата (только category=legal):**

| # | source | text (фрагмент) |
|---|--------|-----------------|
| 1 | Форма_ Договор подряда... | «Заказчик вправе отказаться от исполнения договора...» |
| 2 | Форма_ Договор подряда... | «В случае нарушения Подрядчиком срока выполнения работ...» |
| 3 | Форма_ Договор подряда... | «Сторона вправе расторгнуть договор в одностороннем порядке...» |

Без фильтра в top-3 попадают также чанки из `concession` (КС Вологда содержит похожую терминологию). Фильтр сужает поиск до нужного типа документов.

---

### Фильтр 2 — Range по дате (created_at)

```python
from datetime import datetime, timedelta
from qdrant_client.models import Filter, FieldCondition, DatetimeRange

cutoff = datetime(2024, 3, 1)  # только документы не ранее марта 2024

query_filter = Filter(
    must=[
        FieldCondition(
            key="created_at",
            range=DatetimeRange(gte=cutoff)
        )
    ]
)
results = await store.search(query_vector=qvec, top_k=3, query_filter=query_filter)
```

**Запрос:** «Ответственность сторон за нарушение обязательств»

**Эффект фильтра:** без фильтра первый результат — чанк из КС Вологда (created_at=2024-01-15). С фильтром `gte=2024-03-01` этот документ исключается, в top-3 остаются только чанки из «Договор подряда» (created_at от 2024-03-10) и «Политика оператора» (created_at от 2024-06-01).

---

### Фильтр 3 — Композитный must + must_not

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

query_filter = Filter(
    must=[
        FieldCondition(key="category", match=MatchValue(value="corporate"))
    ],
    must_not=[
        FieldCondition(key="source", match=MatchValue(value="КС Вологда полный текст_маск.docx"))
    ]
)
results = await store.search(query_vector=qvec, top_k=3, query_filter=query_filter)
```

**Запрос:** «Права и обязанности участников общества»

**Логика:** ищем только в корпоративных документах (`category=corporate`), исключая концессионное соглашение. Это типичный production-паттерн: «только тенант X, исключая архивные или нерелевантные источники». В результате top-3 содержит исключительно чанки из «Устав ООО».
