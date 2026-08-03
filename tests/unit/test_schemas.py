import pytest
from pydantic import ValidationError
from app.schemas.chat import ChatRequest

def test_empty_messages_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[])
        
        
from app.schemas.chat import Message

def test_empty_content_rejected():
    with pytest.raises(ValidationError):
        Message(role="user", content="")
        
def test_too_long_content_rejected():
    with pytest.raises(ValidationError):
        Message(role="user", content="а" * 100_001)
        
def test_invalid_role_rejected():
    with pytest.raises(ValidationError):
        Message(role="admin", content="привет")
        
def test_temperature_out_of_range():
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[Message(role="user", content="привет")],
            temperature=3.0,
        )