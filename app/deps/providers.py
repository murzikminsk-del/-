# провайдеры зависимостей для FastAPI DI
from functools import lru_cache  # для кеширования настроек
from fastapi import Request, Depends  # Request - для доступа к app.state, Depends - для DI

from openai import AsyncOpenAI  # async клиент OpenAI
from redis.asyncio import Redis  # async клиент Redis

from app.core.config import get_settings, Settings  # настройки приложения
from app.services.llm_service import LLMService  # сервис с кешем

# достаёт AsyncOpenAI клиент из состояния приложения
def get_openai(request: Request) -> AsyncOpenAI:
    return request.app.state.openai

# достаёт Redis клиент из состояния приложения
def get_cache(request: Request) -> Redis:
    return request.app.state.cache

# собирает LLMService из всех зависимостей
def get_llm_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> LLMService:
    return LLMService(
        openai=get_openai(request),
        cache=get_cache(request),
        settings=settings,
        canary=request.app.state.canary,  # добавлено: секретная метка для output_filter
    )