from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.backend_client import BackendClient

router = Router()

FEEDBACK_PREFIX = "fb"


def feedback_keyboard(message_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👍", callback_data=f"{FEEDBACK_PREFIX}:up:{message_id}")
    kb.button(text="👎", callback_data=f"{FEEDBACK_PREFIX}:down:{message_id}")
    return kb.as_markup()


@router.callback_query(F.data.startswith(f"{FEEDBACK_PREFIX}:"))
async def on_feedback(cb: CallbackQuery, backend: BackendClient) -> None:
    _, vote, msg_id = cb.data.split(":", 2)
    chat_uuid = await backend.get_or_create_chat(
        owner_external_id=str(cb.message.chat.id),
        interface="telegram",
    )
    try:
        await backend.post_feedback(
            chat_id=chat_uuid,
            message_id=msg_id,
            owner_external_id=str(cb.message.chat.id),
            value=vote,
        )
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.answer("Спасибо!" if vote == "up" else "Учтём, разберёмся.")
    except Exception:
        await cb.answer("Не удалось сохранить оценку.")
        
