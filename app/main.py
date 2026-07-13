# точка входа FastAPI приложения
import httpx  # для отключения системного прокси
from contextlib import asynccontextmanager  # для lifespan

from fastapi import FastAPI  # основной класс приложения
from openai import AsyncOpenAI  # async клиент OpenAI
from redis.asyncio import Redis  # async клиент Redis

from app.core.config import get_settings
from app.routers import chat, health, models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # инициализация при старте сервера
    settings = get_settings()
    app.state.openai = AsyncOpenAI(
        api_key=settings.llm.openai_api_key.get_secret_value(),
        timeout=settings.llm.request_timeout,
        max_retries=settings.llm.max_retries,
        http_client=httpx.AsyncClient(trust_env=False),  # игнорируем системный прокси
    )
    app.state.cache = Redis.from_url(settings.redis_url)
    yield
    # закрытие при остановке сервера
    await app.state.openai.close()
    await app.state.cache.aclose()

app = FastAPI(lifespan=lifespan)  # создаём приложение с lifespan

app.include_router(chat.router)
app.include_router(health.router)
app.include_router(models.router)