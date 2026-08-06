# Модуль 4, Блок 1 — Архитектура чата и хранение истории

## Проблема: LLM stateless

LLM не помнит предыдущие запросы. Каждый `chat.completions.create()` — независимый вызов.

**Аналогия:** HTTP тоже stateless. Cookies и сессии добавляют память. Для LLM роль cookies играет массив `messages` плюс наша БД.

**Хрупкость «клиент передаёт messages»:**
- Каждый клиент хранит историю по-своему → дублирование логики, разные форматы
- Два клиента одного пользователя → десинхронизация
- Переустановка клиента → история потеряна
- Модерация, аудит, аналитика — невозможны: нет единого места хранения

---

## Решение: chat живёт в backend

Клиент присылает только `POST /chats/{id}/messages` с текстом. Backend сам собирает контекст из истории.

**Любой клиент — тонкий:** знает только свой UI/транспорт.

**Эволюция по модулям:**
- M4: `ChatService` — history → LLM
- M5: + RAG
- M6: + tools и agent loop

Контракт `/chats/{id}/messages` остаётся стабильным — меняется только то, что внутри.

---

## Chat как доменная сущность

```python
class Chat(BaseModel):
    id: UUID
    owner_external_id: str   # Telegram user_id, email, любой stable id
    interface: str           # "telegram" | "web" | "cli"
    system_prompt: str | None
    created_at: datetime

class ChatMessage(BaseModel):
    id: UUID
    chat_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    tokens: int | None = None
    media_refs: dict | None = None   # заполнится в Б4.3
    prompt_id: UUID | None = None    # заполнится в Б4.4
    created_at: datetime
```

Один пользователь — много чатов (как в ChatGPT или Claude Code: сессии-проекты).

---

## Repository-паттерн

**Зачем:**
- **Независимость хранилища от бизнес-логики** — `ChatService` не знает, JSON это или Postgres
- **Тестируемость** — в тестах подкладываем `JsonChatRepository` с временной папкой, Postgres не нужен
- **Эволюция** — прототип на JSON → переезд на Postgres без изменения контракта сервиса
- **Abstract test suite** — один набор тестов прогоняется против обеих реализаций

### Интерфейс ChatRepository (Protocol)

```python
from typing import Protocol
from uuid import UUID
from app.chat.domain import Chat, ChatMessage

class ChatRepository(Protocol):
    async def create_chat(self, owner_external_id: str, interface: str,
                          system_prompt: str | None = None) -> Chat: ...
    async def get_chat(self, chat_id: UUID) -> Chat | None: ...
    async def get_or_create_chat(self, owner_external_id: str, interface: str) -> Chat: ...
    async def append_message(self, chat_id: UUID, message: ChatMessage) -> ChatMessage: ...
    async def list_messages(self, chat_id: UUID, limit: int = 50) -> list[ChatMessage]: ...
    async def soft_delete_messages(self, chat_id: UUID) -> None: ...
```

**Protocol, не ABC** — не требует наследования. Любой класс с такими методами «является» `ChatRepository`. Структурная типизация Python, дружелюбна к mypy.

`get_or_create_chat` — идемпотентная фабрика по `(owner_external_id, interface)`: бот при каждом сообщении вызывает `POST /chats`, не храня локально `chat_id`.

---

## JsonChatRepository

**Структура на диске:**
```
${CHAT_STORAGE_DIR}/
└── chats/
    ├── 7a1b2c3d-.../
    │   ├── chat.json       # метаданные Chat
    │   └── messages.jsonl  # одна ChatMessage на строку
    └── 9e8f7a6b-.../
        ├── chat.json
        └── messages.jsonl
```

**JSONL — append-only:** новое сообщение = одна строка в конец файла. Никаких parse-rewrite-write циклов. Чтение N последних — `readlines()[-N:]`.

```python
import aiofiles
from pathlib import Path
from uuid import UUID
from app.chat.domain import Chat, ChatMessage

class JsonChatRepository:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    async def append_message(self, chat_id: UUID, message: ChatMessage) -> ChatMessage:
        path = self.base_dir / "chats" / str(chat_id) / "messages.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "a") as f:
            await f.write(message.model_dump_json() + "\n")
        return message

    async def list_messages(self, chat_id: UUID, limit: int = 50) -> list[ChatMessage]:
        path = self.base_dir / "chats" / str(chat_id) / "messages.jsonl"
        if not path.exists():
            return []
        async with aiofiles.open(path) as f:
            lines = await f.readlines()
        return [ChatMessage.model_validate_json(l) for l in lines[-limit:]]
```

`aiofiles` — async-обёртка над файловым IO. Без неё запись в FastAPI блокировала бы event loop.

---

## PostgresChatRepository

### Схема таблиц

```sql
CREATE TABLE chats (
    id UUID PRIMARY KEY,
    owner_external_id TEXT NOT NULL,
    interface TEXT NOT NULL,
    system_prompt TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY,
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    media_refs JSONB,
    tokens INT,
    prompt_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ   -- soft delete
);

-- Индекс только для не удалённых сообщений
CREATE INDEX ix_chat_messages_chat_created
    ON chat_messages (chat_id, created_at DESC)
    WHERE deleted_at IS NULL;
```

**Partial index** (`WHERE deleted_at IS NULL`) — в индексе только активные сообщения. `SELECT ... WHERE chat_id=? ORDER BY created_at DESC LIMIT N` → Index Scan, единицы миллисекунд.

**Soft delete** — не удаляем строки физически, ставим метку `deleted_at`. Даёт право передумать, сохраняет аналитику.

### Реализация (async SQLAlchemy 2.x)

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class PostgresChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def append_message(self, chat_id: UUID, message: ChatMessage) -> ChatMessage:
        row = ChatMessageRow(id=message.id, chat_id=chat_id,
                             role=message.role, content=message.content,
                             tokens=message.tokens)
        self.session.add(row)
        await self.session.commit()
        return ChatMessage.model_validate(row, from_attributes=True)

    async def list_messages(self, chat_id: UUID, limit: int = 50) -> list[ChatMessage]:
        stmt = (
            select(ChatMessageRow)
            .where(ChatMessageRow.chat_id == chat_id,
                   ChatMessageRow.deleted_at.is_(None))
            .order_by(ChatMessageRow.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [ChatMessage.model_validate(r, from_attributes=True) for r in reversed(rows)]
```

`reversed(rows)` — `ORDER BY DESC` отдаёт от новых к старым, LLM ждёт хронологический порядок.

### Когда какую реализацию брать

| Реализация | Когда брать | Когда не подходит |
|---|---|---|
| `JsonChatRepository` | Один пользователь, dev, тесты | Multi-process write, >1k чатов, аналитика |
| `PostgresChatRepository` | Production, multi-user, нужна аналитика и SQL | Прототип без инфраструктуры |

---

## Структура app/chat/

```
app/
├── llm/          # из М3
├── observability/ # из М3
└── chat/         # ← новое в М4Б1
    ├── __init__.py
    ├── domain.py         # Chat, ChatMessage (Pydantic)
    ├── repository.py     # ChatRepository (Protocol)
    ├── repositories/
    │   ├── json_repo.py  # JsonChatRepository
    │   └── pg_repo.py    # PostgresChatRepository + ChatMessageRow ORM
    ├── service.py        # ChatService + context strategies
    ├── routes.py         # /chats endpoints
    └── deps.py           # фабрика репозитория через env var
```

**Один модуль — один слой:** `domain.py` не импортирует инфраструктуру. `repositories/` не знают про FastAPI. `routes.py` оперирует `ChatService`, не репозиторием напрямую.

---

## Endpoints

### POST /chats

```python
router = APIRouter(prefix="/chats", tags=["chats"])

class CreateChatIn(BaseModel):
    owner_external_id: str
    interface: str
    system_prompt: str | None = None

class CreateChatOut(BaseModel):
    chat_id: UUID

@router.post("", response_model=CreateChatOut)
async def create_chat(body: CreateChatIn,
                      chat_service: ChatService = Depends(get_chat_service)):
    chat = await chat_service.get_or_create_chat(
        owner_external_id=body.owner_external_id,
        interface=body.interface,
        system_prompt=body.system_prompt,
    )
    return CreateChatOut(chat_id=chat.id)
```

**Идемпотентно по `(owner_external_id, interface)`** — повторный POST возвращает уже существующий `chat_id`. `system_prompt` применяется только при первом создании.

### POST /chats/{id}/messages — SSE streaming

```python
@router.post("/{chat_id}/messages")
async def post_message(chat_id: UUID,
                       chat_service: ChatService = Depends(get_chat_service),
                       content: str = Form(""),
                       media: UploadFile | None = File(None)):
    async def event_source():
        try:
            async for event in chat_service.send_message(
                chat_id=chat_id, user_content=content, media=media
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(event_source(), media_type="text/event-stream")
```

**SSE-формат — три типа событий:**
- `{"type": "token", "delta": "<chunk>"}` — кусок ответа по мере генерации
- `{"type": "message_saved", "message_id": "<uuid>"}` — сообщение сохранено в репозитории
- `{"type": "done"}` — стрим завершён (всегда, даже при обрыве)

---

## DI: фабрика репозитория через env var

```python
# app/chat/deps.py
async def get_repository(request: Request) -> AsyncIterator[ChatRepository]:
    settings = get_settings()
    if settings.chat_repository == "json":
        yield JsonChatRepository(settings.chat_storage_dir)
        return
    async with request.app.state.session_factory() as session:
        yield PostgresChatRepository(session)

def get_chat_service(
    repo: ChatRepository = Depends(get_repository),
    llm = Depends(get_llm_client),
) -> ChatService:
    return ChatService(repository=repo, llm_client=llm)
```

`CHAT_REPOSITORY=json` → dev/тесты. `CHAT_REPOSITORY=postgres` → production. Перезапуск — другая реализация, сервис не меняется.

---

## Стратегии контекста

### Sliding window (дефолт для ДЗ)

```python
async def context_sliding(repo, chat, window=10) -> list[dict]:
    history = await repo.list_messages(chat.id, limit=window)
    msgs = []
    if chat.system_prompt:
        msgs.append({"role": "system", "content": chat.system_prompt})
    msgs.extend({"role": m.role, "content": m.content} for m in history)
    return msgs
```

- **Плюсы:** просто, предсказуемо, постоянная стоимость
- **Минусы:** бот забывает всё за пределами N сообщений
- **Когда:** FAQ, support, короткие сценарии

### LLM-суммаризация

```python
SUMMARIZE_PROMPT = (
    "Сожми этот диалог в 2-3 предложения. Сохрани: "
    "ключевые темы, имена, числа, принятые решения, нерешённые вопросы. "
    "Стиль — телеграфный."
)

async def summarize(messages: list[dict], llm) -> str:
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    resp = await llm.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "system", "content": SUMMARIZE_PROMPT},
                  {"role": "user", "content": convo}],
        max_tokens=256,
    )
    return resp.choices[0].message.content.strip()
```

20 сообщений (~2000 токенов) → 50–100 токенов. Коэффициент 20–40×.
- **Минусы:** теряются цитаты, точные числа, код. +$0.001 и +200–500 мс на вызов.

### Hybrid (production default)

```python
KEEP_RECENT = 5

async def context_hybrid(repo, chat, llm) -> list[dict]:
    history = await repo.list_messages(chat.id, limit=200)
    if len(history) <= KEEP_RECENT:
        return _as_messages(chat.system_prompt, history)

    old, recent = history[:-KEEP_RECENT], history[-KEEP_RECENT:]
    summary = await summarize([{"role": m.role, "content": m.content} for m in old], llm)

    msgs = []
    if chat.system_prompt:
        msgs.append({"role": "system", "content": chat.system_prompt})
    msgs.append({"role": "system", "content": f"Контекст из предыдущей беседы: {summary}"})
    msgs.extend({"role": m.role, "content": m.content} for m in recent)
    return msgs
```

**Бюджет:** system (~200) + summary (~100) + 5 сообщений (~500) ≈ 800 токенов вместо 5000+. Экономия 5–7×.

---

## Подсчёт токенов и token budget

```python
import tiktoken

enc = tiktoken.get_encoding("o200k_base")  # GPT-4o / GPT-5

def count_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += 4  # ChatML overhead на сообщение
        total += len(enc.encode(m["content"]))
        total += len(enc.encode(m.get("role", "")))
    return total + 2

CONTEXT_WINDOW = 8_000   # практичный лимит, не 1M
RESPONSE_TOKENS = 1_024
SAFETY_MARGIN = 256

def fit_to_budget(messages: list[dict]) -> list[dict]:
    budget = CONTEXT_WINDOW - RESPONSE_TOKENS - SAFETY_MARGIN
    while messages and count_tokens(messages) > budget:
        messages = ([messages[0]] + messages[2:]
                    if messages[0]["role"] == "system" else messages[1:])
    return messages
```

**Правило большого пальца:** русское слово ≈ 2–3 токена, английское — 1–1.3. Русский бот тратит в 1.5–2× больше токенов на ту же мысль.

**Lost in the middle:** на входах >32k токенов модель хуже помнит середину контекста. Практичный лимит — 8–16k, даже если окно модели 1M.

---

## Soft delete и /clear

**Postgres:** `UPDATE chat_messages SET deleted_at = NOW() WHERE chat_id = ?`

**JSON:** маркер `{"type": "soft_delete", "at": "..."}` дописывается в `messages.jsonl`, `list_messages` пропускает всё до последнего маркера.

```python
@router.delete("/{chat_id}/messages")
async def clear_messages(chat_id: UUID,
                         chat_service: ChatService = Depends(get_chat_service)):
    await chat_service.clear_history(chat_id)
    return {"status": "ok"}
```

Hard delete по GDPR-запросу — отдельный endpoint `/forgetme`.

---

## Антипаттерны

| Антипаттерн | Что произойдёт | Как правильно |
|---|---|---|
| История на стороне клиента | Десинхронизация между интерфейсами, дубли логики | Backend chat-сервис как источник правды |
| `ChatService` напрямую дёргает Postgres | Нельзя переключить хранилище без правок сервиса | Зависимость от `ChatRepository` (Protocol) |
| `len(text) // 4` для подсчёта токенов | Промахи на русском (в 1.5–2×) | `tiktoken.get_encoding("o200k_base")` |
| Hard delete по `/clear` | Не отменить ошибочный запрос, нет аналитики | Soft delete: `deleted_at = NOW()` + фильтр на чтении |
| assistant сохранён до завершения стрима | Битая запись, если стрим оборвался | Накопить → закончить → один `append_message` |

---

## Главная мысль

История диалога — это часть backend, не свойство клиента. Один источник правды → любые frontend'ы становятся тонкими.

**Дальше:** Б4.2 — Telegram-бот как тонкий клиент поверх `POST /chats/{id}/messages`.
