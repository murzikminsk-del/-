import json
from typing import AsyncIterator
from uuid import UUID

import httpx


class BackendClient:
    def __init__(self, http: httpx.AsyncClient, admin_token: str = "") -> None:
        self._http = http
        self._headers = {"X-Admin-Token": admin_token} if admin_token else {}

    async def get_or_create_chat(self, owner_external_id: str, interface: str) -> UUID:
        r = await self._http.post(
            "/chats",
            json={"owner_external_id": owner_external_id, "interface": interface},
            headers=self._headers,
        )
        r.raise_for_status()
        return UUID(r.json()["chat_id"])

    async def send_message(
        self,
        chat_id: UUID,
        content: str,
        media: bytes | None = None,
        mime: str | None = None,
    ) -> AsyncIterator[dict]:
        return self._stream_tokens(chat_id, content, media, mime)

    async def _stream_tokens(
        self,
        chat_id: UUID,
        content: str,
        media: bytes | None = None,
        mime: str | None = None,
    ) -> AsyncIterator[dict]:
        if media and mime:
            files = {"file": ("file", media, mime)}
            data = {"content": content}
        else:
            files = None
            data = {"content": content}

        async with self._http.stream(
            "POST", f"/chats/{chat_id}/messages",
            data=data,
            files=files,
            headers=self._headers,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        if isinstance(event, dict):
                            if event.get("type") == "done":
                                break
                            yield event
                    except json.JSONDecodeError:
                        pass   

    async def clear_messages(self, chat_id: UUID) -> None:
        r = await self._http.delete(f"/chats/{chat_id}/messages", headers=self._headers)
        r.raise_for_status()

    async def aclose(self) -> None:
        await self._http.aclose()
        
    async def post_feedback(
        self, chat_id: UUID, message_id: str, owner_external_id: str, value: str
    ) -> None:
        r = await self._http.post(
            f"/chats/{chat_id}/messages/{message_id}/feedback",
            json={"value": value, "owner_external_id": owner_external_id},
        )
        r.raise_for_status()

    async def get_admin_stats(self) -> dict:
        r = await self._http.get("/chats/admin/stats", headers=self._headers)
        r.raise_for_status()
        return r.json()

    async def get_admin_users(self, limit: int = 10) -> list[dict]:
        r = await self._http.get(f"/chats/admin/users?limit={limit}", headers=self._headers)
        r.raise_for_status()
        return r.json()

    async def post_admin_broadcast(self, message: str) -> dict:
        r = await self._http.post(
            "/chats/admin/broadcast",
            json={"message": message, "interface_filter": "telegram"},
            headers=self._headers,
        )
        r.raise_for_status()
        return r.json()
        
