import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.services.backend_client import BackendClient
from bot.services.streaming import stream_to_chat
from bot.services.typing import typing_until

router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message, backend: BackendClient, state: FSMContext) -> None:
    if await state.get_state() is not None:
        return

    stop = asyncio.Event()
    task = asyncio.create_task(typing_until(message.bot, message.chat.id, stop))
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        events = await backend.send_message(chat_id, message.text)
        await stream_to_chat(message, events)
    except Exception:
        await message.answer("Не удалось получить ответ. Попробуйте позже.")
    finally:
        stop.set()
        await task