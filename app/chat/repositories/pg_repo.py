from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.domain import Chat, ChatMessage
from app.chat.repositories.pg_models import ChatRow, ChatMessageRow


class PostgresChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_chat(
        self,
        owner_external_id: str,
        interface: str,
        system_prompt: str | None = None,
    ) -> Chat:
        now = datetime.now(timezone.utc)
        row = ChatRow(
            id=uuid4(),
            owner_external_id=owner_external_id,
            interface=interface,
            system_prompt=system_prompt,
            created_at=now,
        )
        self.session.add(row)
        await self.session.commit()
        return Chat.model_validate(row, from_attributes=True)

    async def get_chat(self, chat_id: UUID) -> Chat | None:
        row = await self.session.get(ChatRow, chat_id)
        if row is None:
            return None
        return Chat.model_validate(row, from_attributes=True)

    async def append_message(self, chat_id: UUID, message: ChatMessage) -> ChatMessage:
        row = ChatMessageRow(
            id=message.id,
            chat_id=chat_id,
            role=message.role,
            content=message.content,
            tokens=message.tokens,
            created_at=message.created_at,
        )
        self.session.add(row)
        await self.session.commit()
        return ChatMessage.model_validate(row, from_attributes=True)

    async def list_messages(self, chat_id: UUID, limit: int = 50) -> list[ChatMessage]:
        stmt = (
            select(ChatMessageRow)
            .where(
                ChatMessageRow.chat_id == chat_id,
                ChatMessageRow.deleted_at.is_(None),
            )
            .order_by(ChatMessageRow.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [
            ChatMessage.model_validate(r, from_attributes=True)
            for r in reversed(rows)
        ]

    async def soft_delete_messages(self, chat_id: UUID) -> None:
        stmt = (
            update(ChatMessageRow)
            .where(
                ChatMessageRow.chat_id == chat_id,
                ChatMessageRow.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.commit()
