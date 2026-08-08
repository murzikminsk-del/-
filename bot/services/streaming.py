from collections.abc import AsyncIterable
from time import monotonic

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message

EDIT_INTERVAL = 0.7


async def stream_to_chat(message: Message, events: AsyncIterable[str]) -> None:
    sent = None
    buffer = ""
    last_edit = 0.0

    async for token in events:
        buffer += token
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

    if sent and buffer:
        try:
            await sent.edit_text(buffer)
        except (TelegramBadRequest, TelegramRetryAfter):
            pass