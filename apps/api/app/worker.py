"""Background worker entrypoint.

Two duties:
- Drain `queue:scan` (attachment ids) and run ClamAV.
- Drain `queue:export` (export request ids) and assemble ZIP.
- Periodic: re-aggregate analytics + execute due erasures + purge raw events.
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone

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
            log.info("periodic_done", purged=n, ts=datetime.now(timezone.utc).isoformat())
        except Exception as e:  # noqa: BLE001
            log.warning("periodic_failed", error=str(e))
        await asyncio.sleep(3600)


async def main() -> None:
    configure_logging()
    log.info("worker_started")
    await asyncio.gather(_drain_scan(), _drain_transcode(), _drain_export(), _periodic())


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
