import hashlib
import json
import time

import structlog

from openai import AsyncOpenAI
from redis.asyncio import Redis

from app.core.config import Settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.observability.pii import redact_pii, prompt_hash

logger = structlog.get_logger("llm-service")

class LLMService:
    def __init__(self, openai: AsyncOpenAI, cache: Redis, settings: Settings):
        self._openai = openai
        self._cache = cache
        self._settings = settings

    async def complete(self, req: ChatRequest) -> ChatResponse:
        key = "chat:" + hashlib.sha256(
            req.model_dump_json(exclude={"user_id", "stream"}).encode()
        ).hexdigest()

        cached = await self._cache.get(key)
        if cached:
            response = ChatResponse.model_validate_json(cached)
            response.cached = True
            return response

        raw_prompt = req.messages[-1].content if req.messages else ""

        start = time.perf_counter()
        result = await self._openai.chat.completions.create(
            model=req.model,
            messages=[m.model_dump() for m in req.messages],
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "llm_request_completed",
            model=result.model,
            input_tokens=result.usage.prompt_tokens if result.usage else None,
            output_tokens=result.usage.completion_tokens if result.usage else None,
            latency_ms=round(latency_ms),
            finish_reason=result.choices[0].finish_reason,
            prompt_hash=prompt_hash(raw_prompt),
            prompt_preview=redact_pii(raw_prompt)[:120],
        )

        response = ChatResponse(
            content=result.choices[0].message.content,
            model=result.model,
            usage=result.usage.model_dump() if result.usage else {},
            finish_reason=result.choices[0].finish_reason,
        )

        await self._cache.setex(
            key,
            self._settings.cache_ttl_seconds,
            response.model_dump_json(),
        )

        return response