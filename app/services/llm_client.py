import asyncio
import json
import logging
import time
import httpx

from openai import AsyncOpenAI

import app.core.logging

from app.core.config import get_settings
settings = get_settings()



class AsyncLLMClient:
    def __init__(self, concurrency: int = 5):
        self._client = AsyncOpenAI(
            api_key=settings.llm.openai_api_key.get_secret_value(),
            timeout=30,
            max_retries=3,
            http_client=httpx.AsyncClient(trust_env=False),    
        )
        self._sem = asyncio.Semaphore(concurrency)
        
    async def complete(self, prompt: str) -> str:
        start = time.perf_counter()
        async with asyncio.timeout(15):
            async with self._sem:
                response = await self._client.chat.completions.create(
                    model=settings.llm.default_model,
                    messages=[{"role": "user", "content": prompt}],
                )
                result = response.choices[0].message.content
                duration_ms = (time.perf_counter() - start) * 1000
                logging.info(f"llm.call duration_ms={duration_ms:.0f} model={settings.llm.default_model} prompt_chars={len(prompt)} status=ok")
                return result
    
    async def batch_chat(self, prompts: list[str], concurrency: int = 5) -> list[str | Exception]:
        coros = [self.complete(prompt) for prompt in prompts]
        return await asyncio.gather(*coros, return_exceptions=True)
    
    async def stream_chat(self, prompt: str):
        stream = await self._client.chat.completions.create(
            model=settings.llm.default_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
                
    
                
