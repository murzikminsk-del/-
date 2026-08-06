from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, Settings
from app.chat.repository import ChatRepository
from app.chat.repositories.json_repo import JsonChatRepository
from app.chat.repositories.pg_repo import PostgresChatRepository
from app.chat.service import ChatService


async def get_repository(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[ChatRepository]:
    if settings.chat_repository == "json":
        settings.chat_storage_dir.mkdir(parents=True, exist_ok=True)
        yield JsonChatRepository(settings.chat_storage_dir)
        return

    if settings.chat_repository == "postgres":
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            yield PostgresChatRepository(session)
        return

    raise ValueError(
        f"Unknown CHAT_REPOSITORY value: '{settings.chat_repository}'. "
        "Expected 'json' or 'postgres'."
    )


def get_chat_service(
    request: Request,
    repo: ChatRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    return ChatService(
        repository=repo,
        llm_client=request.app.state.openai,
        strategy=settings.chat_context_strategy,
        context_window=settings.chat_context_window,
    )
