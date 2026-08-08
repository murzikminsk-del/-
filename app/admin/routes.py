import asyncio
from datetime import datetime, timezone, timedelta
from uuid import UUID

import httpx
import sqlalchemy as sa
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings

log = structlog.get_logger("admin")
router = APIRouter(prefix="/chats/admin", tags=["admin"])


async def require_admin(x_admin_token: str = Header(...)) -> None:
    settings = get_settings()
    if x_admin_token != settings.admin_token.get_secret_value():
        raise HTTPException(status_code=403, detail="forbidden")
    
class StatsOut(BaseModel):
    total_messages: int
    active_users: int
    avg_latency_ms: float
    moderation_block_rate: float
    feedback_up_ratio: float


class UserOut(BaseModel):
    owner_external_id: str
    chat_count: int
    last_seen_at: datetime


class BroadcastIn(BaseModel):
    message: str
    interface_filter: str = "telegram"


class BroadcastOut(BaseModel):
    broadcast_id: int
    total_owners: int


@router.get("/stats", dependencies=[Depends(require_admin)], response_model=StatsOut)
async def get_stats(request: Request) -> StatsOut:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    async with request.app.state.session_factory() as session:
        total = await session.scalar(
            sa.text("SELECT COUNT(*) FROM chat_messages WHERE created_at >= :s AND deleted_at IS NULL"),
            {"s": since},
        )
        active = await session.scalar(
            sa.text("SELECT COUNT(DISTINCT c.owner_external_id) FROM chats c "
                    "JOIN chat_messages m ON m.chat_id = c.id "
                    "WHERE m.created_at >= :s AND m.deleted_at IS NULL"),
            {"s": since},
        )
        up = await session.scalar(
            sa.text("SELECT COUNT(*) FROM message_feedback WHERE value='up' AND created_at >= :s"),
            {"s": since},
        ) or 0
        down = await session.scalar(
            sa.text("SELECT COUNT(*) FROM message_feedback WHERE value='down' AND created_at >= :s"),
            {"s": since},
        ) or 0
    total_fb = up + down
    return StatsOut(
        total_messages=total or 0,
        active_users=active or 0,
        avg_latency_ms=0.0,
        moderation_block_rate=0.0,
        feedback_up_ratio=round(up / total_fb, 3) if total_fb else 0.0,
    )

@router.get("/users", dependencies=[Depends(require_admin)], response_model=list[UserOut])
async def get_users(request: Request, limit: int = 50) -> list[UserOut]:
    async with request.app.state.session_factory() as session:
        rows = await session.execute(
            sa.text(
                "SELECT c.owner_external_id, COUNT(DISTINCT c.id) AS chat_count, "
                "MAX(m.created_at) AS last_seen_at "
                "FROM chats c JOIN chat_messages m ON m.chat_id = c.id "
                "WHERE m.deleted_at IS NULL "
                "GROUP BY c.owner_external_id "
                "ORDER BY last_seen_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [
            UserOut(owner_external_id=r.owner_external_id, chat_count=r.chat_count, last_seen_at=r.last_seen_at)
            for r in rows
        ]


@router.post("/broadcast", dependencies=[Depends(require_admin)], response_model=BroadcastOut)
async def broadcast(body: BroadcastIn, request: Request) -> BroadcastOut:
    settings = get_settings()
    async with request.app.state.session_factory() as session:
        rows = await session.execute(
            sa.text("SELECT DISTINCT owner_external_id FROM chats WHERE interface = :iface"),
            {"iface": body.interface_filter},
        )
        owner_ids = [r.owner_external_id for r in rows]

        result = await session.execute(
            sa.text(
                "INSERT INTO broadcasts (text, total_owners) VALUES (:text, :total) RETURNING id"
            ),
            {"text": body.message, "total": len(owner_ids)},
        )
        broadcast_id = result.scalar()
        await session.commit()

    asyncio.create_task(_send_broadcast(body.message, owner_ids, broadcast_id, settings.bot_url, settings.internal_token.get_secret_value()))
    return BroadcastOut(broadcast_id=broadcast_id, total_owners=len(owner_ids))


async def _send_broadcast(text: str, owner_ids: list[str], broadcast_id: int, bot_url: str, internal_token: str) -> None:
    sent = failed = 0
    async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
        for owner_id in owner_ids:
            try:
                r = await client.post(
                    f"{bot_url}/notify",
                    json={"chat_id": owner_id, "text": text},
                    headers={"X-Internal-Token": internal_token},
                )
                r.raise_for_status()
                sent += 1
            except httpx.HTTPError:
                failed += 1
            await asyncio.sleep(0.04)
    log.info("broadcast_done", broadcast_id=broadcast_id, sent=sent, failed=failed)
    
