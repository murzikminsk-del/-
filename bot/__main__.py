import asyncio
import logging
import ssl

import httpx
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.handlers import routers
from bot.services.backend_client import BackendClient


class NoVerifySession(AiohttpSession):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        self._connector_init["ssl"] = ssl_ctx


async def make_notify_app(bot: Bot) -> web.Application:
    app = web.Application()

    async def notify(request: web.Request) -> web.Response:
        token = request.headers.get("X-Internal-Token", "")
        if token != settings.internal_token.get_secret_value():
            return web.Response(status=403, text="forbidden")
        data = await request.json()
        await bot.send_message(chat_id=data["chat_id"], text=data["text"])
        return web.json_response({"status": "ok"})

    app.router.add_post("/notify", notify)
    return app


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.bot_token.get_secret_value(), session=NoVerifySession())
    dp = Dispatcher(storage=MemoryStorage())

    http = httpx.AsyncClient(
        base_url=settings.backend_url,
        timeout=httpx.Timeout(30.0),
        trust_env=False,
    )
    backend = BackendClient(http, admin_token=settings.admin_token.get_secret_value())
    dp["backend"] = backend

    for router in routers:
        dp.include_router(router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="ask", description="Задать вопрос по теме"),
        BotCommand(command="clear", description="Очистить историю"),
        BotCommand(command="cancel", description="Отменить сценарий"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="stats", description="Статистика (админ)"),
        BotCommand(command="broadcast", description="Рассылка (админ)"),
    ])

    notify_app = await make_notify_app(bot)
    runner = web.AppRunner(notify_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 9000)
    await site.start()

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await backend.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())