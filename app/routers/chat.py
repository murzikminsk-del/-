# Future chat endpoints: /chat, /chat/stream, /chat/batch.
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.llm_client import AsyncLLMClient

router = APIRouter() # создаем роутер
client = AsyncLLMClient() # создаем экземпляр клиента

# SSE-эндпоинт для стриминга ответа по токенам
@router.post("/chat/stream")
async def stream_endpoint(prompt: str):
    async def generate():
        async for token in client.stream_chat(prompt):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")