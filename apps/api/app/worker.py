"""Background worker entrypoint.

Two duties:
- Drain `queue:scan` (attachment ids) and run ClamAV.
- Drain `queue:export` (export request ids) and assemble ZIP.
- Periodic: re-aggregate analytics + execute due erasures + purge raw events.
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime

from app.analytics.worker import purge_raw, reaggregate
from app.content.transcode import needs_transcode, transcode_one
from app.content.uploads import scan_one
from app.core.redis_client import get_redis
from app.core.telemetry import configure_logging, log
from app.legal.erasure import execute_due
from app.legal.export import build_one


async def _drain_scan() -> None:
    r = await get_redis()
    from sqlalchemy import select

    from app.content.models import Attachment
    from app.core.db import session_scope

    while True:
        try:
            res = await r.blpop("queue:scan", timeout=5)
            if not res:
                continue
            _, aid = res
            try:
                await scan_one(aid)
            except Exception as e:  # noqa: BLE001
                log.warning("scan_failed", attachment_id=aid, error=str(e))
                continue
            # After scan: if attachment is a clean video_primary whose mime is
            # not already web-safe MP4, enqueue a transcode job.
            try:
                async with session_scope() as s:
                    att = await s.scalar(select(Attachment).where(Attachment.id == aid))
                if att and att.state == "clean" and att.role == "video_primary" and needs_transcode(att.mime):
                    await r.lpush("queue:transcode", aid)
                    log.info("transcode_enqueued", attachment_id=aid, mime=att.mime)
            except Exception as e:  # noqa: BLE001
                log.warning("transcode_enqueue_failed", attachment_id=aid, error=str(e))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("scan_loop_error", error=str(e))
            await asyncio.sleep(1)


async def _drain_transcode() -> None:
    r = await get_redis()
    while True:
        try:
            res = await r.blpop("queue:transcode", timeout=5)
            if not res:
                continue
            _, aid = res
            try:
                await transcode_one(aid)
            except Exception as e:  # noqa: BLE001
                log.warning("transcode_failed", attachment_id=aid, error=str(e))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("transcode_loop_error", error=str(e))
            await asyncio.sleep(1)


async def _drain_export() -> None:
    r = await get_redis()
    while True:
        try:
            res = await r.blpop("queue:export", timeout=5)
            if not res:
                continue
            _, rid = res
            try:
                await build_one(rid)
            except Exception as e:  # noqa: BLE001
                log.warning("export_failed", request_id=rid, error=str(e))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("export_loop_error", error=str(e))
            await asyncio.sleep(1)


async def _periodic() -> None:
    while True:
        try:
            await reaggregate(days=7)
            n = await purge_raw(retention_days=90)
            await execute_due()
            log.info("periodic_done", purged=n, ts=datetime.now(UTC).isoformat())
        except Exception as e:  # noqa: BLE001
            log.warning("periodic_failed", error=str(e))
        await asyncio.sleep(3600)


async def _alerts_loop() -> None:
    """Every 5 min: check activity windows, email admins if thresholds tripped."""
    from sqlalchemy import select

    from app.core.db import session_scope
    from app.core.security import activity_alerts
    from app.identity.models import User
    from app.notifications.email import send_admin_alert_email

    r = await get_redis()
    while True:
        try:
            async with session_scope() as s:
                fired = await activity_alerts.check_all(r, s)
                if fired:
                    admins = (
                        await s.scalars(
                            select(User).where(User.role == "admin", User.state == "active")
                        )
                    ).all()
                    for alert in fired:
                        log.warning("activity_alert_fired", **alert)
                        for admin in admins:
                            try:
                                await send_admin_alert_email(
                                    admin.email,
                                    event=alert["event"],
                                    count=alert["count"],
                                    threshold=alert["threshold"],
                                    window_s=alert["window_s"],
                                )
                            except Exception as e:  # noqa: BLE001
                                log.warning("alert_email_failed", to=admin.email, error=str(e))
        except Exception as e:  # noqa: BLE001
            log.warning("alerts_loop_error", error=str(e))
        await asyncio.sleep(300)


async def _digest_loop() -> None:
    """Send a per-N-days activity digest to all active admin emails.

    Defaults to every 2 days. Tracks the last-sent timestamp in Redis so a
    worker restart doesn't double-send.
    """
    from sqlalchemy import select, text

    from app.core.db import session_scope
    from app.identity.models import User
    from app.legal.models import PlatformSetting
    from app.notifications.email import send_admin_digest_email

    r = await get_redis()
    while True:
        try:
            async with session_scope() as s:
                enabled_row = await s.scalar(
                    select(PlatformSetting).where(PlatformSetting.key == "digest.enabled")
                )
                enabled = bool(enabled_row.value) if enabled_row else True
                if not enabled:
                    await asyncio.sleep(3600)
                    continue

                interval_row = await s.scalar(
                    select(PlatformSetting).where(PlatformSetting.key == "digest.interval_days")
                )
                interval_days = int(interval_row.value) if interval_row else 2
                interval_s = interval_days * 24 * 3600

                last = await r.get("digest:last_sent")
                now = datetime.now(UTC).timestamp()
                if last and (now - float(last)) < interval_s:
                    await asyncio.sleep(3600)
                    continue

                since_sql = f"NOW() - INTERVAL '{interval_days} days'"
                summary: dict[str, int | str] = {
                    "Period (days)": interval_days,
                }
                summary["New users"] = int(
                    (
                        await s.execute(
                            text(f"SELECT COUNT(*) FROM users WHERE created_at >= {since_sql}")
                        )
                    ).scalar_one()
                )
                summary["Items published"] = int(
                    (
                        await s.execute(
                            text(
                                f"SELECT COUNT(*) FROM items WHERE state='published' AND published_at >= {since_sql}"
                            )
                        )
                    ).scalar_one()
                )
                summary["Signup-flood trips"] = int(
                    (
                        await s.execute(
                            text(
                                f"SELECT COUNT(*) FROM audit_log WHERE action='security.signup_flood_triggered' AND ts >= {since_sql}"
                            )
                        )
                    ).scalar_one()
                )
                summary["Activity alerts"] = int(
                    (
                        await s.execute(
                            text(
                                f"SELECT COUNT(*) FROM audit_log WHERE action='security.activity_alert_triggered' AND ts >= {since_sql}"
                            )
                        )
                    ).scalar_one()
                )
                summary["Failed logins"] = int(
                    (
                        await s.execute(
                            text(
                                f"SELECT COUNT(*) FROM audit_log WHERE action='user.login.fail' AND ts >= {since_sql}"
                            )
                        )
                    ).scalar_one()
                )

                admins = (
                    await s.scalars(
                        select(User).where(User.role == "admin", User.state == "active")
                    )
                ).all()
                for admin in admins:
                    try:
                        await send_admin_digest_email(
                            admin.email, period_days=interval_days, summary=summary
                        )
                    except Exception as e:  # noqa: BLE001
                        log.warning("digest_email_failed", to=admin.email, error=str(e))

                await r.set("digest:last_sent", str(now))
                log.info("digest_sent", period_days=interval_days, admins=len(admins))
        except Exception as e:  # noqa: BLE001
            log.warning("digest_loop_error", error=str(e))
        await asyncio.sleep(3600)


async def main() -> None:
    configure_logging()
    log.info("worker_started")
    await asyncio.gather(
        _drain_scan(),
        _drain_transcode(),
        _drain_export(),
        _periodic(),
        _alerts_loop(),
        _digest_loop(),
    )


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
