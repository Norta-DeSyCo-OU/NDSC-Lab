"""Daily aggregation + raw-event retention."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.analytics.models import DailyContributorAggregate, DailyItemAggregate, RawViewEvent
from app.core.db import session_scope


async def reaggregate(days: int = 7) -> None:
    """Idempotent re-aggregation of trailing N days (D-17)."""
    async with session_scope() as s:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        await s.execute(
            delete(DailyItemAggregate).where(DailyItemAggregate.day >= cutoff.date())
        )
        await s.execute(
            delete(DailyContributorAggregate).where(DailyContributorAggregate.day >= cutoff.date())
        )

        # by item
        rows = (
            await s.execute(
                select(
                    func.date(RawViewEvent.qualifying_ts).label("d"),
                    RawViewEvent.item_id,
                    func.count("*").label("n"),
                )
                .where(RawViewEvent.qualifying_ts >= cutoff)
                .group_by("d", RawViewEvent.item_id)
            )
        ).all()
        for d, item_id, n in rows:
            await s.execute(
                pg_insert(DailyItemAggregate)
                .values(day=d, item_id=item_id, views=int(n))
                .on_conflict_do_update(
                    index_elements=["day", "item_id"],
                    set_={"views": int(n)},
                )
            )

        # by contributor
        rows2 = (
            await s.execute(
                select(
                    func.date(RawViewEvent.qualifying_ts).label("d"),
                    RawViewEvent.contributor_user_id,
                    func.count("*").label("n"),
                )
                .where(RawViewEvent.qualifying_ts >= cutoff)
                .group_by("d", RawViewEvent.contributor_user_id)
            )
        ).all()
        for d, cu, n in rows2:
            await s.execute(
                pg_insert(DailyContributorAggregate)
                .values(day=d, contributor_user_id=cu, views=int(n))
                .on_conflict_do_update(
                    index_elements=["day", "contributor_user_id"],
                    set_={"views": int(n)},
                )
            )


async def purge_raw(retention_days: int = 90) -> int:
    """FR-VIEW-006: drop raw events older than retention_days. Returns rows deleted."""
    async with session_scope() as s:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        r = await s.execute(delete(RawViewEvent).where(RawViewEvent.qualifying_ts < cutoff))
        return r.rowcount or 0
