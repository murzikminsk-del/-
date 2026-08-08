from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import settings
from bot.services.backend_client import BackendClient

router = Router()


class IsAdmin:
    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False
        return message.from_user.id in settings.bot_admin_ids


router.message.filter(IsAdmin())


@router.message(Command("stats"))
async def cmd_stats(message: Message, backend: BackendClient) -> None:
    try:
        s = await backend.get_admin_stats()
        await message.answer(
            f"<b>Статистика 24ч</b>\n"
            f"Сообщений: <code>{s.get('total_messages', 0)}</code>\n"
            f"DAU: <code>{s.get('active_users', 0)}</code>\n"
            f"Feedback ratio: <code>{s.get('feedback_up_ratio', 0):.1%}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"Ошибка получения статистики: {e}")


@router.message(Command("users"))
async def cmd_users(message: Message, backend: BackendClient) -> None:
    try:
        users = await backend.get_admin_users(limit=10)
        if not users:
            await message.answer("Пользователей пока нет.")
            return
        lines = ["<b>Последние пользователи:</b>"]
        for u in users:
            lines.append(f"• <code>{u['owner_external_id']}</code> — чатов: {u['chat_count']}")
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, backend: BackendClient) -> None:
    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer("Использование: /broadcast <текст>")
        return
    try:
        result = await backend.post_admin_broadcast(text)
        await message.answer(
            f"Рассылка запущена. ID: {result['broadcast_id']}, получателей: {result['total_owners']}"
        )
    except Exception as e:
        await message.answer(f"Ошибка рассылки: {e}")