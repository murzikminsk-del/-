import time

from aiogram import F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import Message

from bot.services.backend_client import BackendClient

router = Router()


async def _stream_response(message: Message, backend: BackendClient, chat_id, content: str, media: bytes | None = None, mime: str | None = None) -> None:
    placeholder = await message.answer("...")
    buffer = ""
    last_edit = time.time()
    async for token in await backend.send_message(chat_id, content, media=media, mime=mime):
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


@router.message(F.photo)
async def handle_photo(message: Message, backend: BackendClient) -> None:
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        buf = await message.bot.download_file(file.file_path)
        content = message.caption or "Опиши это изображение"
        await _stream_response(message, backend, chat_id, content, media=buf.read(), mime="image/jpeg")
    except Exception:
        await message.answer("Не удалось обработать изображение. Попробуйте позже.")


@router.message(F.voice)
async def handle_voice(message: Message, backend: BackendClient) -> None:
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        file = await message.bot.get_file(message.voice.file_id)
        buf = await message.bot.download_file(file.file_path)
        await _stream_response(message, backend, chat_id, "Ответь на это голосовое сообщение", media=buf.read(), mime="audio/ogg")
    except Exception:
        await message.answer("Не удалось обработать голосовое сообщение. Попробуйте позже.")


@router.message(F.document)
async def handle_document(message: Message, backend: BackendClient) -> None:
    try:
        chat_id = await backend.get_or_create_chat(
            owner_external_id=str(message.chat.id),
            interface="telegram",
        )
        doc = message.document
        mime = doc.mime_type or "application/octet-stream"
        file = await message.bot.get_file(doc.file_id)
        buf = await message.bot.download_file(file.file_path)
        content = message.caption or "Проанализируй содержимое документа"
        await _stream_response(message, backend, chat_id, content, media=buf.read(), mime=mime)
    except Exception:
        await message.answer("Не удалось обработать документ. Попробуйте позже.")