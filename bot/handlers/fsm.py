import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import topics_kb
from bot.services.backend_client import BackendClient
from bot.services.streaming import stream_to_chat
from bot.services.typing import typing_until
from bot.states import AskFlow

router = Router()


@router.message(Command("ask"))
async def start_ask(message: Message, state: FSMContext) -> None:
    await message.answer("Выберите тему:", reply_markup=topics_kb())
    await state.set_state(AskFlow.waiting_for_topic)


@router.callback_query(AskFlow.waiting_for_topic, F.data.startswith("topic:"))
async def on_topic(callback: CallbackQuery, state: FSMContext) -> None:
    slug = callback.data.split(":", 1)[1]
    if slug == "cancel":
        await state.clear()
        await callback.message.edit_text("Сценарий отменён.")
    else:
        await state.update_data(topic=slug)
        await state.set_state(AskFlow.waiting_for_question)
        await callback.message.edit_text(f"Тема: {slug}. Введите вопрос:")
    await callback.answer()


@router.message(AskFlow.waiting_for_question, F.text)
async def on_question(message: Message, state: FSMContext, backend: BackendClient) -> None:
    data = await state.get_data()
    prompt = f"Тема: {data['topic']}. Вопрос: {message.text}"
    stop = asyncio.Event()
    task = asyncio.create_task(typing_until(message.bot, message.chat.id, stop))
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        events = await backend.send_message(chat_id, prompt)
        await stream_to_chat(message, events)
    except Exception:
        await message.answer("Не удалось получить ответ. Попробуйте позже.")
    finally:
        stop.set()
        await task
        await state.clear()