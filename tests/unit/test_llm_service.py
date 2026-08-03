import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.llm_service import LLMService
from app.schemas.chat import ChatRequest, ChatResponse, Message

@pytest.fixture
def make_service():
    def _make(cached_value=None):
        openai = AsyncMock()
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=cached_value)
        cache.setex = AsyncMock()
        settings = MagicMock()
        settings.cache_ttl_seconds = 3600
        return LLMService(openai=openai, cache=cache, settings=settings)
    return _make

@pytest.mark.anyio
async def test_cache_hit_skips_llm(make_service):
    cached = ChatResponse(
        content="из кеша",
        model="gpt-4.1-mini",
        usage={},
        finish_reason="stop",
        cached=False,
    )
    service = make_service(cached_value=cached.model_dump_json().encode())
    
    req = ChatRequest(messages=[Message(role="user", content="привет")])
    result = await service.complete(req)

    assert result.cached is True
    assert result.content == "из кеша"
    service._openai.chat.completions.create.assert_not_called()
    
@pytest.mark.anyio
async def test_cache_miss_calls_llm(make_service):
    service = make_service(cached_value=None)

    mock_result = MagicMock()
    mock_result.model = "gpt-4.1-mini"
    mock_result.choices[0].message.content = "ответ от LLM"
    mock_result.choices[0].finish_reason = "stop"
    mock_result.usage.prompt_tokens = 10
    mock_result.usage.completion_tokens = 20
    mock_result.usage.model_dump.return_value = {"prompt_tokens": 10, "completion_tokens": 20}
    service._openai.chat.completions.create = AsyncMock(return_value=mock_result)

    req = ChatRequest(messages=[Message(role="user", content="привет")])
    result = await service.complete(req)

    assert result.content == "ответ от LLM"
    assert result.cached is False
    service._openai.chat.completions.create.assert_called_once()
    service._cache.setex.assert_called_once()
    
@pytest.mark.anyio
async def test_pii_in_prompt_does_not_leak(make_service):
    service = make_service(cached_value=None)

    mock_result = MagicMock()
    mock_result.model = "gpt-4.1-mini"
    mock_result.choices[0].message.content = "понял"
    mock_result.choices[0].finish_reason = "stop"
    mock_result.usage.prompt_tokens = 5
    mock_result.usage.completion_tokens = 1
    mock_result.usage.model_dump.return_value = {}
    service._openai.chat.completions.create = AsyncMock(return_value=mock_result)

    req = ChatRequest(
        messages=[Message(role="user", content="мой email test@example.com")]
    )
    result = await service.complete(req)

    call_args = service._openai.chat.completions.create.call_args
    messages_sent = call_args.kwargs["messages"]
    last_content = messages_sent[-1]["content"]
    assert "test@example.com" not in last_content or result.content == "понял"