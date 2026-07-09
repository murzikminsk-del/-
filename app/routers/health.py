# Future health endpoints: /health and /ready.
# Смысл: здесь позже будут проверки, что приложение запущено и готово принимать запросы.

from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}