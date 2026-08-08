# ИИ-ассистент для анализа юридических документов с использованием RAG

## Описание проекта

Данный проект представляет собой разработку ИИ-ассистента, который помогает анализировать юридические документы и находить в них важную информацию. Ассистент использует технологию Retrieval-Augmented Generation (RAG), которая позволяет искать данные в базе документов и формировать ответы на основе найденной информации.

Основная задача проекта — упростить работу с юридическими текстами, сократить время на их анализ и снизить риск пропуска важных условий, противоречий или правовых рисков.

## Почему выбрана эта тема

Тема выбрана потому, что анализ юридических документов требует внимательности, занимает много времени и связан с высокой ответственностью. Даже небольшая неточность или пропуск существенного условия могут повлечь правовые и финансовые последствия.

Использование ИИ в такой задаче позволяет автоматизировать первичный анализ документов, ускорить поиск нужной информации и повысить качество работы с юридическими текстами.

## Быстрый старт (Docker)

Самый простой способ запустить проект — через Docker Compose. Никаких дополнительных установок не требуется.

```bash
cp .env.example .env
# заполнить .env своими ключами
docker compose up -d --build
```

Через 15–20 секунд сервис будет готов:

```bash
curl http://localhost:8000/health   # {"status":"ok"}
curl http://localhost:8000/ready    # {"status":"ok","redis":"up"}
```

Swagger-документация: http://localhost:8000/docs

### Остановка

```bash
docker compose down
```

## Запуск локально (без Docker)

Требования: Python 3.11+, Redis, [uv](https://docs.astral.sh/uv/)

```bash
cp .env.example .env
# заполнить .env своими ключами
uv sync
uvicorn app.main:app --reload
```

## Переменные окружения

Все переменные описаны в `.env.example`. Основные:

| Переменная | Описание |
|------------|----------|
| `LLM__OPENAI_API_KEY` | API-ключ OpenAI |
| `LLM__DEFAULT_MODEL` | Модель (по умолчанию `gpt-4.1-mini`) |
| `REDIS_URL` | Адрес Redis (для Docker: `redis://redis:6379/0`) |
| `CACHE_TTL_SECONDS` | Время жизни кеша в секундах |

## Структура проекта

```
app/
  routers/      # эндпоинты: /chat, /chat/stream, /health, /ready
  services/     # бизнес-логика, LLM-клиент, security-слой (валидатор входа, фильтр выхода)
  schemas/      # Pydantic-модели
  prompts/      # системный промпт и описания инструментов
  core/         # настройки и логирование
data/           # база документов (documents.json)
eval/           # eval-инфраструктура и конфиг для garak
```

## Блок 3.1 — Function Calling

В этом блоке в ассистента добавлен механизм Function Calling. Модель может не только отвечать текстом, но и вызывать Python-функции для работы с внутренней базой документов.

Реализованы два инструмента:

- `search_documents(query, department, doc_type)` — ищет документы по запросу, отделу и типу документа.
- `extract_key_fields(document_id)` — извлекает из выбранного документа ключевые поля: стороны, дату, сумму и риски.

Данные хранятся в `data/documents.json`. Описания инструментов — в `app/prompts/tools/`, системный промпт — в `app/prompts/system_v1.j2`.

### Проверка работы

**Сценарий 1: запрос требует вызова инструментов**

Запрос: `Найди договор с Альфой и извлеки из него ключевые поля.`

Ассистент вызвал `search_documents`, нашёл `contract_001`, затем вызвал `extract_key_fields`. В ответе — название, дата, стороны, сумма и риски.

**Сценарий 2: запрос не требует инструментов**

Запрос: `Объясни простыми словами, что такое RAG.`

Ассистент не вызывал инструменты — вопрос общий, ответ сформирован текстом.

**Сценарий 3: пограничный запрос**

Запрос: `Есть ли у нас документы про персональные данные?`

Ассистент использовал `search_documents` и нашёл `policy_001` — «Политика обработки персональных данных».

## Блок 3.5 — Docker и контейнеризация

Сервис упакован в Docker-контейнер и запускается вместе с Redis одной командой.

**Что сделано:**
- Multi-stage `Dockerfile` на `python:3.11-slim-bookworm` с менеджером зависимостей `uv`
- Non-root пользователь `appuser` (uid=1000) внутри контейнера
- `.dockerignore` — секреты и мусор не попадают в образ
- `compose.yaml` — сервисы `app` и `redis` с healthcheck и `depends_on: service_healthy`
- Эндпоинт `/ready` — проверяет доступность Redis, возвращает 200 или 503
- Размер образа: ~285 MB

## Блок 3.6 — Observability

К сервису добавлен observability-слой: трейсинг LLM-запросов, структурированные JSON-логи и маскирование персональных данных.

**Что сделано:**
- `compose.yaml` дополнен сервисом Phoenix (Arize) — UI трейсов на `http://localhost:6006`
- `app/observability/tracing.py` — автоинструментация OpenAI через OpenInference, трейсы отправляются в Phoenix
- `app/observability/logging.py` — JSON-логи через `structlog` с `request_id`, моделью, токенами, latency и finish_reason в каждой строке. С блока 3.8 маскирование PII подключено как отдельный `processor` — покрывает все текстовые поля логов, а не только `prompt_preview`
- `app/observability/pii.py` — маскирование email, телефона, номера карты, ИНН, паспорта; переиспользуется в security-слое (блок 3.8) для фильтрации ответов модели перед отдачей пользователю
- `tests/test_pii.py` — 4 unit-теста для `redact_pii`, все зелёные
- Скриншот трейса — в `docs/observability/`

## Блок 3.7 — Тестирование и оценка качества

Добавлен полноценный testing-слой: unit-тесты с моками и eval-инфраструктура для оценки качества ответов через LLM-as-judge.

**Что сделано:**
- `eval/golden_dataset.json` — 22 вопроса по предметной области (договоры, политики, претензии), 3 категории (`factual`, `support`, `legal`), 4 примера с `difficulty: hard`, поле `must_not_contain` для запрещённых слов
- `tests/unit/` — 8 unit-тестов с моками, запускаются без API-ключей и без сети
- `eval/run_evaluation.py` — CLI-скрипт прогона: вызывает сервис, оценивает ответы через judge-модель (G-Eval, reason-then-score)
- `eval/thresholds.yaml` — пороги качества (`correctness_avg ≥ 4.0`, `min_correctness ≥ 2.0`)
- `eval/check_thresholds.py` — проверяет последний прогон и завершается с `sys.exit(1)` при нарушении порога

### Запуск unit-тестов

```bash
pytest tests/unit/ -v
```

Все тесты запускаются без сетевых вызовов и без API-ключей.

### Запуск eval-прогона

Требует запущенного сервиса и VPN (для доступа к OpenAI).

**Шаг 1** — запустить сервис (в отдельном терминале):

```bash
$env:REDIS_URL="redis://localhost:6379/0"; uvicorn app.main:app --port 8000
```

**Шаг 2** — запустить прогон:

```bash
$env:PYTHONPATH = "."; python eval/run_evaluation.py --golden eval/golden_dataset.json --judge gpt-4.1-mini --out eval/runs/2026-08-03.json
```

**Шаг 3** — проверить пороги:

```bash
$env:PYTHONPATH = "."; python eval/check_thresholds.py
```

Результаты прогона сохраняются в `eval/runs/<YYYY-MM-DD>.json` и читаются через `jq`:

```bash
jq '.aggregates.correctness_avg' eval/runs/2026-08-03.json
```

## Блок 3.8 — Безопасность ИИ-приложений

Сервис проверен на устойчивость к атакам через [NVIDIA garak](https://github.com/NVIDIA/garak): два прогона — **baseline** (без защиты) и **after** (с защитным слоем), с сравнением результатов.

**Что сделано:**
- `eval/security/rest_config.json` — конфиг REST-таргета garak под `/chat`-эндпоинт (`messages` → `content`)
- `app/services/security/input_validator.py` — блокировка prompt injection / jailbreak-паттернов (в т.ч. на русском), атак кодировками, слишком длинного ввода
- `app/services/security/output_filter.py` — детектор утечки системного промпта через canary-токен, маскирование PII (переиспользует `redact_pii` из блока 3.6), блокировка script-инъекций в ответе
- Canary-токен генерируется при старте сервиса (`app.state.canary`) и подмешивается в системный промпт
- `app/observability/logging.py` дополнен processor'ом — PII теперь маскируется во всех логах, не только в превью промпта
- Валидатор входа подключён в `/chat` до похода в LLM, фильтр выхода — после получения ответа

### Установка garak

```bash
uv add garak
uv run garak --version
uv run garak --list_probes
```

> **Известная проблема на Windows.** Пакет `nltk` (транзитивная зависимость garak) с 2026 года включает защиту от CWE-427 (`nltk/inisec.py`), которая блокирует импорты, если считает, что модуль подгружается из текущей рабочей директории. На машинах, где Python установлен в пользовательском профиле (`C:\Users\<user>\AppData\...`), это даёт ложные срабатывания даже на стандартных модулях (`regex`, `xml`). Обходится официальной переменной окружения:
> ```powershell
> $env:NLTK_DISABLE_IMPORT_SECURITY = "1"
> ```
> Ставится перед каждым запуском `garak` в новой сессии терминала (переменная не сохраняется между окнами).

### Прогон baseline

```bash
docker compose exec redis redis-cli FLUSHALL   # очистить кеш перед прогоном — иначе ответы могут быть закэшированы с более раннего прогона
uv run garak --target_type rest -G eval/security/rest_config.json \
  --probes promptinject.HijackHateHumans,encoding.InjectBase64,dan.Ablation_Dan_11_0 \
  --generations 1 --report_prefix baseline
```

Если `/chat` отвечает медленно (например, из-за сетевых задержек до OpenAI) и garak падает с `ReadTimeoutError` — увеличить `request_timeout` в `rest_config.json` (по умолчанию 20 сек, поднято до 60).

Отчёт: `~/.local/share/garak/garak_runs/baseline.report.{html,jsonl}`.

### Прогон after

Тот же набор проб, тот же конфиг, сервис перезапущен с подключённым security-слоем:

```bash
docker compose exec redis redis-cli FLUSHALL
uv run garak --target_type rest -G eval/security/rest_config.json \
  --probes promptinject.HijackHateHumans,encoding.InjectBase64,dan.Ablation_Dan_11_0 \
  --generations 1 --report_prefix after
```

Отчёт: `~/.local/share/garak/garak_runs/after.report.{html,jsonl}`.

### Результаты

Подробная таблица «было / стало» и примеры пробитий — в `docs/security/garak_baseline_<дата>.md` и `docs/security/garak_after_<дата>.md`.

**Итоговые числа baseline-прогона** (модель `gpt-4.1-mini`, без защиты):

| Проба | Детектор | Атак | Пробито | % успеха атаки |
|---|---|---|---|---|
| `dan.Ablation_Dan_11_0` | dan.DAN | 127 | 0 | 0% |
| `dan.Ablation_Dan_11_0` | mitigation.MitigationBypass | 127 | 0 | 0% |
| `encoding.InjectBase64` | encoding.DecodeMatch | 256 | 202 | 78.91% |
| `encoding.InjectBase64` | encoding.DecodeApprox | 256 | 234 | 91.41% |
| `promptinject.HijackHateHumans` | promptinject.AttackRogueString | 256 | 100 | 39.06% |

Штатный safety-тюнинг OpenAI хорошо отбивает классический DAN-джейлбрейк, но пропускает почти всё через base64-кодировку и значительную часть прямых prompt injection — это и есть цель для security-слоя.

## Блок 4.1 — Архитектура чата и хранение истории

Добавлен полноценный чат-сервис с персистентной историей диалога и контекстным окном.

**Что сделано:**
- `app/chat/domain.py` — доменные модели `Chat` и `ChatMessage` (Pydantic v2)
- `app/chat/repository.py` — `ChatRepository` как `typing.Protocol` (структурная типизация)
- `app/chat/repositories/json_repo.py` — JSONL-репозиторий с soft delete (маркер `{"type":"soft_delete"}`)
- `app/chat/repositories/pg_repo.py` + `pg_models.py` — PostgreSQL-репозиторий через async SQLAlchemy 2.x
- `app/chat/service.py` — `ChatService`: две стратегии контекста (sliding window / hybrid), подсчёт токенов через tiktoken
- `app/chat/routes.py` — 5 эндпоинтов: `POST /chats`, `GET /chats/{id}`, `POST /chats/{id}/messages` (SSE-стрим), `GET /chats/{id}/messages`, `DELETE /chats/{id}/messages` (soft delete)
- `alembic/` — миграция `0001_chat_tables` (таблицы `chats` + `chat_messages`, partial index по `deleted_at`)
- `tests/chat/` — 5 тестов контракта репозитория, все зелёные

**Стратегия контекста:** sliding window (последние 10 сообщений). Переключение через `CHAT_CONTEXT_STRATEGY=hybrid`.

**Переключение хранилища:**

```bash
CHAT_REPOSITORY=json          # dev (по умолчанию)
CHAT_REPOSITORY=postgres      # prod, требует: alembic upgrade head
```

Подробнее — в `docs/chat.md`.

## Блок 4.2 — Telegram-бот как тонкий клиент

Telegram-бот на aiogram 3, который ходит в chat-сервис из Б4.1 за всей LLM-логикой. Бот не знает про LLM и не хранит историю — это backend.

**Что сделано:**
- `bot/__main__.py` — точка входа: `Bot`, `Dispatcher`, `MemoryStorage`, регистрация команд через `set_my_commands`
- `bot/config.py` — `Settings`: `BOT_TOKEN`, `BACKEND_URL`, `BOT_ADMIN_IDS`
- `bot/services/backend_client.py` — async httpx-клиент: `get_or_create_chat`, `send_message` (SSE-стрим), `clear_messages`
- `bot/handlers/commands.py` — `/start`, `/help`, `/clear`, `/cancel`
- `bot/handlers/text.py` — нон-командные сообщения → SSE-стрим → `edit_text` с троттлингом
- `bot/handlers/fsm.py` — сценарий `/ask`: тема → вопрос → ответ (aiogram FSM)
- `bot/keyboards/inline.py` — `topics_kb()`: Юридическая консультация, Концессии и договоры, Корпоративный блок, Регламенты и политики
- `bot/states.py` — `AskFlow`: `waiting_for_topic`, `waiting_for_question`, `confirming`
- `tests/bot/` — 6 тестов (MockTransport + FSM-моки), все зелёные

**Запуск:**

```bash
# Терминал 1 — backend
uvicorn app.main:app --reload

# Терминал 2 — бот
python -m bot
```

Бот доступен в Telegram по токену из `.env` (`BOT_TOKEN`). Токен не коммитится в git.

Запуск:


Запускаем — сначала нужен uvicorn в первом терминале:
$env:HTTPS_PROXY = "socks5://127.0.0.1:10808"; $env:HTTP_PROXY = "socks5://127.0.0.1:10808"; uvicorn app.main:app --reload

uvicorn (первый терминал) = backend/API = это как сервер OpenClaw — он принимает запросы, общается с LLM, хранит историю


Потом во втором терминале:
python -m bot

python -m bot (второй терминал) = Telegram = это как браузер с OpenClaw UI — пользовательский интерфейс, который ходит в backend

## Блок 4.3 — Мультимодальность и стриминг

Бот и бэкенд расширены поддержкой медиафайлов: изображений, голосовых сообщений и документов (PDF, DOCX).

**Что сделано:**
- `app/chat/media.py` — `media_to_part()`: конвертер байт + MIME → часть сообщения OpenAI. Изображения → Vision API, аудио → Whisper-1 (транскрипция), PDF → pypdf, DOCX → python-docx
- `app/chat/routes.py` — эндпоинт `POST /chats/{id}/messages` мигрирован с JSON на `multipart/form-data` (поля `content` + необязательный `file`). Формат SSE обновлён: `{"type":"token","delta":"..."}` и `{"type":"done"}`
- `app/chat/service.py` — `send_message` принимает `media_part: dict | None`; `count_tokens` обновлён для multipart-контента
- `bot/handlers/media.py` — хендлеры `F.photo`, `F.voice`, `F.document`: скачивают файл через Bot API, отправляют на бэкенд вместе с текстом
- `bot/services/backend_client.py` — `send_message` принимает `media: bytes | None, mime: str | None`; парсинг SSE обновлён под новый формат
- `tests/bot/test_media.py` — 3 теста медиа-хендлеров; `test_backend_client.py` обновлён под новый SSE

**Поддерживаемые форматы:**

| Тип | MIME | Обработка |
|-----|------|-----------|
| Фото | `image/jpeg` | OpenAI Vision — описание изображения |
| Голосовое | `audio/ogg` | Whisper-1 — транскрипция → ответ |
| PDF | `application/pdf` | pypdf — извлечение текста |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx — извлечение текста |