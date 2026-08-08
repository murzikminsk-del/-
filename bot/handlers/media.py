import asyncio
import httpx

from aiogram import F, Router
from aiogram.types import Message

from bot.services.backend_client import BackendClient
from bot.services.streaming import stream_to_chat
from bot.services.typing import typing_until

from bot.handlers.feedback import feedback_keyboard

router = Router()


async def _send_media(
    message: Message,
    backend: BackendClient,
    content: str,
    media: bytes,
    mime: str,
) -> None:
    stop = asyncio.Event()
    task = asyncio.create_task(typing_until(message.bot, message.chat.id, stop))
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        events = await backend.send_message(chat_id, content, media=media, mime=mime)
        sent, msg_id = await stream_to_chat(message, events)
        if sent and msg_id:
            try:
                await sent.edit_reply_markup(reply_markup=feedback_keyboard(msg_id))
            except Exception:
                pass  # не критично если кнопки не прикрепились
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            await message.answer("Ваш запрос заблокирован — он нарушает правила использования.")
        else:
            await message.answer("Не удалось получить ответ. Попробуйте позже.")
    except Exception:
        await message.answer("Не удалось получить ответ. Попробуйте позже.")


@router.message(F.photo)
async def handle_photo(message: Message, backend: BackendClient) -> None:
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    buf = await message.bot.download_file(file.file_path)
    content = message.caption or "Опиши это изображение"
    await _send_media(message, backend, content, buf.read(), "image/jpeg")


@router.message(F.voice)
async def handle_voice(message: Message, backend: BackendClient) -> None:
    file = await message.bot.get_file(message.voice.file_id)
    buf = await message.bot.download_file(file.file_path)
    await _send_media(message, backend, "Ответь на это голосовое сообщение", buf.read(), "audio/ogg")


@router.message(F.document)
async def handle_document(message: Message, backend: BackendClient) -> None:
    doc = message.document
    mime = doc.mime_type or "application/octet-stream"
    file = await message.bot.get_file(doc.file_id)
    buf = await message.bot.download_file(file.file_path)
    content = message.caption or "Проанализируй содержимое документа"
    await _send_media(message, backend, content, buf.read(), mime)