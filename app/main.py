import httpx
import secrets
import time
import uuid

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from contextlib import asynccontextmanager
from fastapi import FastAPI
from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import get_settings
from app.observability.tracing import setup_tracing
from app.observability.logging import setup_logging
from app.routers import chat, health, models
from app.chat.routes import router as chat_router

setup_logging()

logger = structlog.get_logger("llm-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_tracing()
    app.state.openai = AsyncOpenAI(
        api_key=settings.llm.openai_api_key.get_secret_value(),
        timeout=settings.llm.request_timeout,
        max_retries=settings.llm.max_retries,
        http_client=httpx.AsyncClient(trust_env=False, verify=False),
    )
    app.state.cache = Redis.from_url(settings.redis_url, protocol=2)
    app.state.canary = "CANARY_" + secrets.token_hex(4)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.db_engine = engine

    yield

    await app.state.openai.close()
    await app.state.cache.aclose()
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def logging_middleware(request, call_next):
    clear_contextvars()
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    request.state.request_id = request_id
    bind_contextvars(
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("http_request_completed", status=response.status_code, duration_ms=round(duration_ms))
    response.headers["X-Request-ID"] = request_id
    return response

app.include_router(chat.router)
app.include_router(health.router)
app.include_router(models.router)
app.include_router(chat_router)