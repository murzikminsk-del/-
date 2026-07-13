# роутер для эндпоинтов чата
from fastapi import APIRouter, Depends  # Depends - для dependency injection
from fastapi.responses import StreamingResponse  # для стриминга ответа

from app.deps.providers import get_llm_service  # DI провайдер сервиса
from app.services.llm_service import LLMService  # сервис с кешем
from app.schemas.chat import ChatRequest, ChatResponse  # схемы

router = APIRouter()  # создаём роутер



# эндпоинт для обычного ответа с кешированием
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, service: LLMService = Depends(get_llm_service)):
    return await service.complete(req)

# SSE-эндпоинт для стриминга ответа по токенам
@router.post("/chat/stream")
async def stream_endpoint(req: ChatRequest, service: LLMService = Depends(get_llm_service)):
    async def generate():
        async for token in service._client.stream_chat(req.messages[0].content):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")