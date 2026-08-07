import json
from typing import AsyncIterator
from uuid import UUID

import httpx


class BackendClient:
    def __init__(self, http: httpx.AsyncClient, admin_token: str = "") -> None:
        self._http = http
        self._headers = {"X-Admin-Token": admin_token} if admin_token else {}

    async def get_or_create_chat(
        self, owner_external_id: str, interface: str
    ) -> UUID:
        r = await self._http.post(
            "/chats",
            json={"owner_external_id": owner_external_id, "interface": interface},
            headers=self._headers,
        )
        r.raise_for_status()
        return UUID(r.json()["chat_id"])

    async def send_message(
        self, chat_id: UUID, content: str
    ) -> AsyncIterator[str]:
        return self._stream_tokens(chat_id, content)

    async def _stream_tokens(
        self, chat_id: UUID, content: str
    ) -> AsyncIterator[str]:
        async with self._http.stream(
            "POST",
            f"/chats/{chat_id}/messages",
            json={"content": content},
            headers=self._headers,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        token = json.loads(data)
                        if isinstance(token, str):
                            yield token
                    except json.JSONDecodeError:
                        pass

    async def clear_messages(self, chat_id: UUID) -> None:
        r = await self._http.delete(
            f"/chats/{chat_id}/messages",
            headers=self._headers,
        )
        r.raise_for_status()

    async def aclose(self) -> None:
        await self._http.aclose()
        
        