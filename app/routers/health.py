from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/ready")
async def ready(request: Request):
    try:
        await request.app.state.cache.ping()
        return {"status": "ok", "redis": "up"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "redis": "down"},
        )