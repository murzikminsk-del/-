# сервис для работы с LLM с кешированием через Redis
import hashlib  # для генерации ключа кеша
import json  # для сериализации данных

from openai import AsyncOpenAI  # async клиент OpenAI
from redis.asyncio import Redis  # async клиент Redis

from app.core.config import Settings  # настройки приложения
from app.schemas.chat import ChatRequest, ChatResponse  # схемы запроса и ответа

class LLMService:
    def __init__(self, openai: AsyncOpenAI, cache: Redis, settings: Settings):
        self._openai = openai   # клиент OpenAI
        self._cache = cache     # клиент Redis для кеша
        self._settings = settings  # настройки приложения
        
    async def complete(self, req: ChatRequest) -> ChatResponse:
        # генерируем ключ кеша из параметров запроса
        key = "chat:" + hashlib.sha256(
            req.model_dump_json(exclude={"user_id", "stream"}).encode()
        ).hexdigest()
        
        # проверяем есть ли ответ в кеше
        cached = await self._cache.get(key)
        if cached:
            response = ChatResponse.model_validate_json(cached)
            response.cached = True
            return response
        
        # если кеша нет — идём в OpenAI
        result = await self._openai.chat.completions.create(
            model=req.model,
            messages=[m.model_dump() for m in req.messages],
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        
        # формируем ответ
        response = ChatResponse(
            content=result.choices[0].message.content,
            model=result.model,
            usage=result.usage.model_dump() if result.usage else {},
            finish_reason=result.choices[0].finish_reason,
        )
        
        # сохраняем в кеш
        await self._cache.setex(
            key,
            self._settings.cache_ttl_seconds,
            response.model_dump_json(),
        )
        
        return response