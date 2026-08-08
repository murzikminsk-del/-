from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: SecretStr
    backend_url: str = "http://localhost:8000"
    admin_token: SecretStr = SecretStr("")
    bot_admin_ids: list[int] = []
    internal_token: SecretStr = SecretStr("")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()