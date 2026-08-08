import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.chat.domain import Chat, ChatMessage
from app.chat.deps import get_chat_service
from app.chat.media import media_to_part
from app.chat.service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])


class CreateChatIn(BaseModel):
    owner_external_id: str
    interface: str
    system_prompt: str | None = None


class CreateChatOut(BaseModel):
    chat_id: UUID


@router.post("", response_model=CreateChatOut)
async def create_chat(
    body: CreateChatIn,
    chat_service: ChatService = Depends(get_chat_service),
) -> CreateChatOut:
    chat = await chat_service.create_chat(
        owner_external_id=body.owner_external_id,
        interface=body.interface,
        system_prompt=body.system_prompt,
    )
    return CreateChatOut(chat_id=chat.id)


@router.get("/{chat_id}", response_model=Chat)
async def get_chat(
    chat_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
) -> Chat:
    chat = await chat_service.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@router.post("/{chat_id}/messages")
async def post_message(
    chat_id: UUID,
    request: Request,
    content: str = Form(...),
    file: UploadFile | None = File(default=None),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    media_part = None
    if file is not None:
        file_bytes = await file.read()
        mime = file.content_type or "application/octet-stream"
        media_part = await media_to_part(file_bytes, mime, request.app.state.openai)

    async def event_source():
        try:
            async for chunk in chat_service.send_message(
                chat_id=chat_id, user_content=content, media_part=media_part
            ):
                yield f"data: {json.dumps({'type': 'token', 'delta': chunk}, ensure_ascii=False)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.get("/{chat_id}/messages", response_model=list[ChatMessage])
async def list_messages(
    chat_id: UUID,
    limit: int = 50,
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ChatMessage]:
    return await chat_service._repo.list_messages(chat_id, limit=limit)


@router.delete("/{chat_id}/messages")
async def clear_messages(
    chat_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
) -> dict:
    await chat_service.clear_history(chat_id)
    return {"status": "ok"}