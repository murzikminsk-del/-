import time

from aiogram import F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import Message

from bot.services.backend_client import BackendClient

router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message, backend: BackendClient) -> None:
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        placeholder = await message.answer("...")
        buffer = ""
        last_edit = time.time()
        async for token in await backend.send_message(chat_id, message.text):
            buffer += token
            if time.time() - last_edit >= 0.05:
                try:
                    await placeholder.edit_text(buffer)
                    last_edit = time.time()
                except TelegramRetryAfter:
                    pass
        if buffer:
            try:
                await placeholder.edit_text(buffer)
            except Exception as e:
                if "message is not modified" not in str(e):
                    raise
    except Exception:
        await message.answer("Не удалось получить ответ. Попробуйте позже.")