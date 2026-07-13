# Future chat schemas: ChatRequest, ChatResponse, Message.
# Смысл: здесь позже будут описаны структуры данных для чата: что приходит от пользователя и что возвращает ассистент.

from typing import Annotated, Literal  # Annotated - добавляет ограничения к типам, Literal - перечень допустимых значений
from pydantic import BaseModel, Field, model_validator  # BaseModel - базовый класс схемы, Field - ограничения полей, model_validator - валидатор

# перечень допустимых ролей — другие значения вызовут ошибку
Role = Literal["system", "user", "assistant", "tool"]

# схема одного сообщения
class Message(BaseModel):
    role: Role  # роль отправителя — только из списка Role
    content: Annotated[str, Field(min_length=1, max_length=100_000)]  # текст от 1 до 100000 символов
    
# схема запроса от пользователя
class ChatRequest(BaseModel):
    messages: Annotated[list[Message], Field(min_length=1, max_length=50)]  # список сообщений от 1 до 50
    model: str = "gpt-4.1-mini"                                              # модель по умолчанию
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.7              # температура от 0.0 до 2.0
    max_tokens: Annotated[int, Field(ge=1, le=16_000)] = 1024               # максимум токенов
    stream: bool = False                                                      # стриминг выключен по умолчанию
    user_id: str | None = None                                                # необязательный ID пользователя
    
# схема ответа от ассистента
class ChatResponse(BaseModel):
    content: str                    # текст ответа
    model: str                      # модель которая ответила
    usage: dict                     # статистика токенов
    finish_reason: str              # причина завершения генерации
    cached: bool = False            # был ли ответ из кеша