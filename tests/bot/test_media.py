from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from bot.handlers.media import handle_photo, handle_voice, handle_document


def make_message(chat_id: int = 123) -> MagicMock:
    message = MagicMock()
    message.chat.id = chat_id
    message.answer = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    message.bot = MagicMock()
    message.bot.get_file = AsyncMock(return_value=MagicMock(file_path="file/path"))
    message.bot.download_file = AsyncMock(return_value=BytesIO(b"fake-bytes"))
    return message


def make_backend(chat_id: UUID = UUID("550e8400-e29b-41d4-a716-446655440000")) -> MagicMock:
    backend = MagicMock()
    backend.get_or_create_chat = AsyncMock(return_value=chat_id)

    async def fake_stream(*args, **kwargs):
        yield "ответ"

    backend.send_message = AsyncMock(return_value=fake_stream())
    return backend


@pytest.mark.asyncio
async def test_handle_photo_calls_send_message():
    message = make_message()
    message.photo = [MagicMock(file_id="photo123")]
    message.caption = "что на фото?"
    backend = make_backend()

    await handle_photo(message, backend)

    backend.send_message.assert_called_once()
    _, kwargs = backend.send_message.call_args
    assert kwargs["mime"] == "image/jpeg"
    assert kwargs["media"] == b"fake-bytes"


@pytest.mark.asyncio
async def test_handle_voice_calls_send_message():
    message = make_message()
    message.voice = MagicMock(file_id="voice456")
    backend = make_backend()

    await handle_voice(message, backend)

    backend.send_message.assert_called_once()
    _, kwargs = backend.send_message.call_args
    assert kwargs["mime"] == "audio/ogg"


@pytest.mark.asyncio
async def test_handle_document_calls_send_message():
    message = make_message()
    message.document = MagicMock(
        file_id="doc789",
        mime_type="application/pdf",
    )
    message.caption = None
    backend = make_backend()

    await handle_document(message, backend)

    backend.send_message.assert_called_once()
    _, kwargs = backend.send_message.call_args
    assert kwargs["mime"] == "application/pdf"