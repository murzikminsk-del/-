# роутер для эндпоинтов чата
from fastapi import APIRouter, Depends  # Depends - для dependency injection
from fastapi.responses import StreamingResponse  # для стриминга ответа
from app.services.llm_client import AsyncLLMClient  # наш async клиент
from app.deps.providers import get_llm_client  # DI провайдер клиента

router = APIRouter()  # создаём роутер

# SSE-эндпоинт для стриминга ответа по токенам
@router.post("/chat/stream")
async def stream_endpoint(prompt: str, client: AsyncLLMClient = Depends(get_llm_client)):  # client приходит через DI
    async def generate():
        async for token in client.stream_chat(prompt):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")

# эндпоинт для обычного синхронного ответа
@router.post("/chat")
async def chat_endpoint(prompt: str, client: AsyncLLMClient = Depends(get_llm_client)):  # client приходит через DI
    result = await client.complete(prompt)
    return {"content": result}