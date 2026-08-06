import pytest
import pytest_asyncio
from uuid import uuid4
from pathlib import Path

from app.chat.domain import Chat, ChatMessage
from app.chat.repositories.json_repo import JsonChatRepository


@pytest_asyncio.fixture(params=["json"])
async def repo(request, tmp_path):
    if request.param == "json":
        return JsonChatRepository(base_dir=tmp_path)


@pytest.mark.asyncio
async def test_create_and_get_chat(repo):
    chat = await repo.create_chat(
        owner_external_id="user-1",
        interface="cli",
    )
    found = await repo.get_chat(chat.id)
    assert found is not None
    assert found.id == chat.id
    assert found.owner_external_id == "user-1"


@pytest.mark.asyncio
async def test_append_and_list_messages_chronological(repo):
    chat = await repo.create_chat(owner_external_id="user-1", interface="cli")

    msg1 = ChatMessage(chat_id=chat.id, role="user", content="Привет")
    msg2 = ChatMessage(chat_id=chat.id, role="assistant", content="Здравствуй")

    await repo.append_message(chat.id, msg1)
    await repo.append_message(chat.id, msg2)

    messages = await repo.list_messages(chat.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_list_messages_limit_returns_last(repo):
    chat = await repo.create_chat(owner_external_id="user-1", interface="cli")

    for i in range(5):
        msg = ChatMessage(chat_id=chat.id, role="user", content=f"Сообщение {i}")
        await repo.append_message(chat.id, msg)

    messages = await repo.list_messages(chat.id, limit=3)
    assert len(messages) == 3
    assert messages[-1].content == "Сообщение 4"


@pytest.mark.asyncio
async def test_soft_delete_hides_messages(repo):
    chat = await repo.create_chat(owner_external_id="user-1", interface="cli")

    msg = ChatMessage(chat_id=chat.id, role="user", content="Удали меня")
    await repo.append_message(chat.id, msg)

    await repo.soft_delete_messages(chat.id)
    messages = await repo.list_messages(chat.id)
    assert messages == []

    new_msg = ChatMessage(chat_id=chat.id, role="user", content="Новое сообщение")
    await repo.append_message(chat.id, new_msg)
    messages = await repo.list_messages(chat.id)
    assert len(messages) == 1
    assert messages[0].content == "Новое сообщение"


@pytest.mark.asyncio
async def test_get_unknown_chat_returns_none(repo):
    result = await repo.get_chat(uuid4())
    assert result is None