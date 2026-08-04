# роутер для эндпоинтов чата
from fastapi import APIRouter, Depends, HTTPException  # + HTTPException
from fastapi.responses import StreamingResponse  # для стриминга ответа

from app.deps.providers import get_llm_service  # DI провайдер сервиса
from app.services.llm_service import LLMService  # сервис с кешем
from app.schemas.chat import ChatRequest, ChatResponse  # схемы
from app.services.security.input_validator import validate_input  # добавлено
from app.services.security.output_filter import filter_output  # добавлено

router = APIRouter()  # создаём роутер


# эндпоинт для обычного ответа с кешированием
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, service: LLMService = Depends(get_llm_service)):
    # проверка входа — до похода в LLM
    last_user_text = req.messages[-1].content if req.messages else ""
    check = validate_input(last_user_text)
    if not check.ok:
        raise HTTPException(status_code=400, detail={"code": "input_blocked", "reason": check.reason})

    result = await service.complete(req)

    # проверка выхода — после получения ответа модели
    try:
        result.content = filter_output(result.content, service.render_system_prompt(), service._canary)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return result

# SSE-эндпоинт для стриминга ответа по токенам
@router.post("/chat/stream")
async def stream_endpoint(req: ChatRequest, service: LLMService = Depends(get_llm_service)):
    async def generate():
        async for token in service._client.stream_chat(req.messages[0].content):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")