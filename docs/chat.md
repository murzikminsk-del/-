# Chat — архитектура и хранение истории

## Архитектура

```mermaid
graph LR
    Client-->|POST /chats\nPOST /chats/id/messages|routes.py
    routes.py-->|Depends|ChatService
    ChatService-->|ChatRepository|JsonRepo
    ChatService-->|ChatRepository|PgRepo
    ChatService-->|stream|OpenAI
    JsonRepo-->|JSONL|Disk[(var/chats/)]
    PgRepo-->|AsyncSession|Postgres[(PostgreSQL)]
```

## Стратегия контекста: sliding window

Выбрана стратегия **sliding window** (последние N сообщений).

Обоснование: на текущем этапе проект — RAG-ассистент для работы с документами,
где типичный диалог короткий (вопрос → ответ по документу). Sliding window
достаточна: пользователь задаёт вопросы по конкретному документу, длинная
история не накапливается. Переход на hybrid будет оправдан в M5, когда
появится RAG и диалоги станут длиннее.

Настройка через env: `CHAT_CONTEXT_WINDOW=10` (дефолт).

## Переключение хранилища

JSON (dev, по умолчанию):

    CHAT_REPOSITORY=json
    CHAT_STORAGE_DIR=./var/chats

Postgres (production):

    CHAT_REPOSITORY=postgres
    DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/rag

После смены на postgres — применить миграцию:

    alembic upgrade head

## Endpoints — примеры

**Создать чат:**

    Invoke-WebRequest -Method POST -Uri http://localhost:8000/chats
      -ContentType "application/json"
      -Body '{"owner_external_id":"user-1","interface":"cli"}'
      -UseBasicParsing

**Отправить сообщение (стрим):**

    Invoke-WebRequest -Method POST
      -Uri http://localhost:8000/chats/{chat_id}/messages
      -ContentType "application/json"
      -Body '{"content":"Привет, меня зовут Аня"}'
      -UseBasicParsing

**История сообщений:**

    Invoke-WebRequest -Method GET
      -Uri "http://localhost:8000/chats/{chat_id}/messages"
      -UseBasicParsing

**Очистить историю (soft delete):**

    Invoke-WebRequest -Method DELETE
      -Uri "http://localhost:8000/chats/{chat_id}/messages"
      -UseBasicParsing

**Метаданные чата:**

    Invoke-WebRequest -Method GET
      -Uri "http://localhost:8000/chats/{chat_id}"
      -UseBasicParsing
