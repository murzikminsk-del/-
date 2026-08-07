import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.services.backend_client import BackendClient

log = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, backend: BackendClient) -> None:
    try:
        await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        await message.answer(
            f"Привет, {message.from_user.full_name}!\n"
            "Просто напишите вопрос — отвечу.\n"
            "/clear — очистить историю\n"
            "/ask — задать вопрос по теме\n"
            "/help — справка"
        )
    except Exception:
        log.exception("cmd_start failed")
        await message.answer("Не удалось подключиться к сервису. Попробуйте позже.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "/start — начать работу\n"
        "/clear — очистить историю диалога\n"
        "/ask — задать вопрос по теме\n"
        "/cancel — отменить текущий сценарий\n"
        "/help — эта справка"
    )


@router.message(Command("clear"))
async def cmd_clear(message: Message, backend: BackendClient) -> None:
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        await backend.clear_messages(chat_id)
        await message.answer("История очищена. Можете задать новый вопрос.")
    except Exception:
        await message.answer("Не удалось очистить историю. Попробуйте позже.")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять — вы не в сценарии.")
        return
    await state.clear()
    await message.answer("Сценарий отменён.")