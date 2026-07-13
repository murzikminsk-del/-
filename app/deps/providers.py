# Future dependency providers: get_llm_client, get_cache, get_settings.
# смысл: здесь позже будут функции, которые будут создавать и возвращать объекты для работы с LLM, кэшем и настройками. Эти функции будут использоваться в роутерах для получения нужных зависимостей.

from functools import lru_cache  # для кеширования настроек
from app.core.config import get_settings, Settings  # настройки приложения
from app.services.llm_client import AsyncLLMClient  # наш async клиент

def get_llm_client() -> AsyncLLMClient:  # возвращает экземпляр async клиента
    settings = get_settings()
    return AsyncLLMClient()