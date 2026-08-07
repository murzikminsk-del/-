import time

from aiogram import F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import topics_kb
from bot.services.backend_client import BackendClient
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
async def on_question(
    message: Message,
    state: FSMContext,
    backend: BackendClient,
) -> None:
    data = await state.get_data()
    prompt = f"Тема: {data['topic']}. Вопрос: {message.text}"
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        placeholder = await message.answer("...")
        buffer = ""
        last_edit = time.time()
        async for token in await backend.send_message(chat_id, prompt):
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
    finally:
        await state.clear()