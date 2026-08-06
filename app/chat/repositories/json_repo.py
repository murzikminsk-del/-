import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import aiofiles

from app.chat.domain import Chat, ChatMessage

_SOFT_DELETE_TYPE = "soft_delete"


class JsonChatRepository:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def _chat_dir(self, chat_id: UUID) -> Path:
        return self.base_dir / "chats" / str(chat_id)

    def _chat_file(self, chat_id: UUID) -> Path:
        return self._chat_dir(chat_id) / "chat.json"

    def _messages_file(self, chat_id: UUID) -> Path:
        return self._chat_dir(chat_id) / "messages.jsonl"

    async def create_chat(
        self,
        owner_external_id: str,
        interface: str,
        system_prompt: str | None = None,
    ) -> Chat:
        chat = Chat(
            owner_external_id=owner_external_id,
            interface=interface,
            system_prompt=system_prompt,
        )
        chat_dir = self._chat_dir(chat.id)
        chat_dir.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self._chat_file(chat.id), "w", encoding="utf-8") as f:
            await f.write(chat.model_dump_json())
        return chat

    async def get_chat(self, chat_id: UUID) -> Chat | None:
        path = self._chat_file(chat_id)
        if not path.exists():
            return None
        async with aiofiles.open(path, encoding="utf-8") as f:
            data = await f.read()
        return Chat.model_validate_json(data)

    async def append_message(self, chat_id: UUID, message: ChatMessage) -> ChatMessage:
        path = self._messages_file(chat_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            await f.write(message.model_dump_json() + "\n")
        return message

    async def list_messages(self, chat_id: UUID, limit: int = 50) -> list[ChatMessage]:
        path = self._messages_file(chat_id)
        if not path.exists():
            return []
        async with aiofiles.open(path, encoding="utf-8") as f:
            lines = await f.readlines()

        # найти последний soft-delete маркер и пропустить всё до него
        last_delete_idx = -1
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == _SOFT_DELETE_TYPE:
                    last_delete_idx = i
            except json.JSONDecodeError:
                continue

        active_lines = lines[last_delete_idx + 1:]

        messages = []
        for line in active_lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == _SOFT_DELETE_TYPE:
                    continue
                messages.append(ChatMessage.model_validate_json(line))
            except (json.JSONDecodeError, Exception):
                continue

        return messages[-limit:]

    async def soft_delete_messages(self, chat_id: UUID) -> None:
        path = self._messages_file(chat_id)
        if not path.exists():
            return
        marker = json.dumps(
            {"type": _SOFT_DELETE_TYPE, "at": datetime.now(timezone.utc).isoformat()}
        )
        async with aiofiles.open(path, "a", encoding="utf-8") as f:
            await f.write(marker + "\n")
