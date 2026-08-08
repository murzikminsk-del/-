import tiktoken
from typing import AsyncIterator
from uuid import UUID

from app.chat.domain import Chat, ChatMessage
from app.chat.repository import ChatRepository

_enc = tiktoken.get_encoding("o200k_base")

CONTEXT_WINDOW = 8_000
RESPONSE_TOKENS = 1_024
SAFETY_MARGIN = 256

SUMMARIZE_PROMPT = (
    "Сожми этот диалог в 2-3 предложения. Сохрани: "
    "ключевые темы, имена, числа, принятые решения, нерешённые вопросы. "
    "Стиль — телеграфный."
)

KEEP_RECENT = 5


def count_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += 4
        content = m["content"]
        if isinstance(content, str):
            total += len(_enc.encode(content))
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    total += len(_enc.encode(part["text"]))
        total += len(_enc.encode(m.get("role", "")))
    return total + 2


def fit_to_budget(messages: list[dict]) -> list[dict]:
    budget = CONTEXT_WINDOW - RESPONSE_TOKENS - SAFETY_MARGIN
    while messages and count_tokens(messages) > budget:
        if messages[0]["role"] == "system":
            messages = [messages[0]] + messages[2:]
        else:
            messages = messages[1:]
    return messages


def _as_messages(system_prompt: str | None, history: list[ChatMessage]) -> list[dict]:
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.extend({"role": m.role, "content": m.content} for m in history)
    return msgs


class ChatService:
    def __init__(
        self,
        repository: ChatRepository,
        llm_client,
        strategy: str = "sliding",
        context_window: int = 10,
    ):
        self._repo = repository
        self._llm = llm_client
        self._strategy = strategy
        self._context_window = context_window

    async def create_chat(
        self,
        owner_external_id: str,
        interface: str,
        system_prompt: str | None = None,
    ) -> Chat:
        return await self._repo.create_chat(owner_external_id, interface, system_prompt)

    async def get_chat(self, chat_id: UUID) -> Chat | None:
        return await self._repo.get_chat(chat_id)

    async def _build_context(self, chat: Chat) -> list[dict]:
        if self._strategy == "hybrid":
            return await self._context_hybrid(chat)
        return await self._context_sliding(chat)

    async def _context_sliding(self, chat: Chat) -> list[dict]:
        history = await self._repo.list_messages(chat.id, limit=self._context_window)
        return _as_messages(chat.system_prompt, history)

    async def _context_hybrid(self, chat: Chat) -> list[dict]:
        history = await self._repo.list_messages(chat.id, limit=200)
        if len(history) <= KEEP_RECENT:
            return _as_messages(chat.system_prompt, history)

        old, recent = history[:-KEEP_RECENT], history[-KEEP_RECENT:]
        old_msgs = [{"role": m.role, "content": m.content} for m in old]
        summary = await self._summarize(old_msgs)

        msgs = []
        if chat.system_prompt:
            msgs.append({"role": "system", "content": chat.system_prompt})
        msgs.append({"role": "system", "content": f"Контекст из предыдущей беседы: {summary}"})
        msgs.extend({"role": m.role, "content": m.content} for m in recent)
        return msgs

    async def _summarize(self, messages: list[dict]) -> str:
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        resp = await self._llm.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SUMMARIZE_PROMPT},
                {"role": "user", "content": convo},
            ],
            max_tokens=256,
        )
        return resp.choices[0].message.content.strip()

    async def send_message(
        self, chat_id: UUID, user_content: str, media_part: dict | None = None) -> AsyncIterator[str]:
        chat = await self._repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat {chat_id} not found")

        user_msg = ChatMessage(chat_id=chat_id, role="user", content=user_content)
        await self._repo.append_message(chat_id, user_msg)

        messages = await self._build_context(chat)
        if media_part:
            messages.append({"role": "user", "content": [
                {"type": "text", "text": user_content},
                media_part,
            ]})
        else:
            messages.append({"role": "user", "content": user_content})
        messages = fit_to_budget(messages)
        
        full_response = []
        stream = await self._llm.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            stream=True,
        )
                       
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_response.append(delta)
                yield delta

        assistant_text = "".join(full_response)
        if assistant_text:
            assistant_msg = ChatMessage(
                chat_id=chat_id, role="assistant", content=assistant_text
            )
            await self._repo.append_message(chat_id, assistant_msg)

    async def clear_history(self, chat_id: UUID) -> None:
        await self._repo.soft_delete_messages(chat_id)
