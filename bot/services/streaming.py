from collections.abc import AsyncIterable
from time import monotonic

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message

EDIT_INTERVAL = 0.7


async def stream_to_chat(
    message: Message, events: AsyncIterable[dict]
) -> tuple[Message | None, str | None]:
    sent = None
    buffer = ""
    last_edit = 0.0
    message_id: str | None = None

    async for event in events:
        if event.get("type") == "token":
            buffer += event.get("delta", "")
            if sent is None:
                sent = await message.answer(buffer)
                last_edit = monotonic()
            elif monotonic() - last_edit >= EDIT_INTERVAL:
                try:
                    await sent.edit_text(buffer)
                    last_edit = monotonic()
                except TelegramRetryAfter as e:
                    last_edit = monotonic() + e.retry_after
                except TelegramBadRequest:
                    last_edit = monotonic()
        elif event.get("type") == "message_saved":
            message_id = event.get("message_id")

    if sent and buffer:
        try:
            await sent.edit_text(buffer)
        except (TelegramBadRequest, TelegramRetryAfter):
            pass

    return sent, message_id