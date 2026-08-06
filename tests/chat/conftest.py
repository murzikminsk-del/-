import pytest
import pytest_asyncio
from pathlib import Path
from uuid import uuid4

from app.chat.repositories.json_repo import JsonChatRepository


@pytest.fixture
def tmp_json_repo(tmp_path):
    return JsonChatRepository(base_dir=tmp_path)


@pytest_asyncio.fixture
async def json_repo(tmp_path):
    return JsonChatRepository(base_dir=tmp_path)