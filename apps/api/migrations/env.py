"""Alembic environment."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.models_base import Base
from app.core.settings import get_settings

# Import all models so Base.metadata is populated.
from app.identity import models as _id_models  # noqa: F401
from app.certification import models as _cert_models  # noqa: F401
from app.content import models as _content_models  # noqa: F401
from app.curation import models as _curation_models  # noqa: F401
from app.comments import models as _comments_models  # noqa: F401
from app.analytics import models as _analytics_models  # noqa: F401
from app.legal import models as _legal_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return get_settings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    cfg: dict[str, Any] = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _url()
    engine = async_engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
