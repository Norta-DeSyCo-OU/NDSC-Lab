"""Analytics routes: view event ingest + admin dashboards."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import DailyContributorAggregate, DailyItemAggregate, RawViewEvent
from app.content.models import Item
from app.core.db import get_session
from app.core.policy import Actor
from app.core.redis_client import get_redis
from app.core.security.csrf import require_csrf
from app.core.security.rate_limit import hit
from app.core.settings import get_settings
from app.identity.deps import require_admin, require_user
from app.identity.models import CookieConsent

router = APIRouter(tags=["analytics"])


class ViewIn(BaseModel):
    item_id: str
    item_type: str = Field(pattern="^(video|article|teaching_material)$")
    view_session_uuid: UUID
    watched_s: float | None = Field(default=None, ge=0)
    scroll_pct: float | None = Field(default=None, ge=0, le=1)


@router.post("/events/view")
async def record_view(
    body: ViewIn,
    request: Request,
    response: Response,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    require_csrf(request)
    settings = get_settings()

    # FR-VIEW-001 (D-05): strict origin allowlist (exact-match of scheme://host[:port]).
    # `startswith` was vulnerable to lookalikes like `https://evil.com.allowed.com`.
    from urllib.parse import urlparse

    raw = request.headers.get("origin") or request.headers.get("referer") or ""
    p = urlparse(raw)
    origin_norm = f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""
    allowed = {o.rstrip("/") for o in settings.allowed_origins}
    if origin_norm not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="bad_origin")

    # D-14: analytics opt-in required
    consent = await s.scalar(
        select(CookieConsent)
        .where(CookieConsent.user_id == actor.user_id)
        .order_by(desc(CookieConsent.created_at))
        .limit(1)
    )
    if not consent or not consent.analytics:
        return Response(status_code=204)

    # FR-VIEW-001 (D-05): rate limit 30/min/user
    r = await get_redis()
    await hit(
        r,
        bucket=f"view:user:{actor.user_id}",
        limit=settings.rate_limit_view_event_per_user_min,
        window_s=60,
    )

    item = await s.scalar(select(Item).where(Item.id == body.item_id))
    if not item or item.state != "published":
        return Response(status_code=204)

    # Threshold checks (FR-VIEW-002,003) — admin tunables stub: use defaults
    if body.item_type == "video":
        if body.watched_s is None or body.watched_s < 10:
            return Response(status_code=204)
    else:
        if (body.watched_s or 0) < 5 or (body.scroll_pct or 0) < 0.25:
            return Response(status_code=204)

    # Dedup window 30 min (FR-VIEW-004)
    key = f"view:dedup:{actor.user_id}:{body.item_id}:{int(datetime.now(UTC).timestamp() // 1800)}"
    acquired = await r.set(key, "1", ex=1800, nx=True)
    if not acquired:
        return Response(status_code=204)

    s.add(
        RawViewEvent(
            user_id=actor.user_id,
            item_id=item.id,
            item_type=item.type,
            contributor_user_id=item.author_id,
            view_session_uuid=body.view_session_uuid,
            qualifying_ts=datetime.now(UTC),
            data={"watched_s": body.watched_s, "scroll_pct": body.scroll_pct},
        )
    )
    return Response(status_code=204)


@router.get("/admin/analytics/items")
async def items_dashboard(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
) -> list[dict]:
    rows = (
        await s.execute(
            select(DailyItemAggregate.item_id, func.sum(DailyItemAggregate.views).label("views"))
            .group_by(DailyItemAggregate.item_id)
            .order_by(desc("views"))
            .limit(limit)
        )
    ).all()
    return [{"item_id": r[0], "views": int(r[1])} for r in rows]


@router.get("/admin/analytics/contributors")
async def contributors_dashboard(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
) -> list[dict]:
    rows = (
        await s.execute(
            select(
                DailyContributorAggregate.contributor_user_id,
                func.sum(DailyContributorAggregate.views).label("views"),
            )
            .group_by(DailyContributorAggregate.contributor_user_id)
            .order_by(desc("views"))
            .limit(limit)
        )
    ).all()
    return [{"contributor_user_id": r[0], "views": int(r[1])} for r in rows]
