"""Structured logging + Sentry + Prometheus."""
from __future__ import annotations

import logging
import sys

import sentry_sdk
import structlog
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.settings import get_settings


def configure_logging() -> None:
    s = get_settings()
    logging.basicConfig(
        level=s.log_level,
        format="%(message)s",
        stream=sys.stdout,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(s.log_level)
        ),
        cache_logger_on_first_use=True,
    )


def init_sentry() -> None:
    s = get_settings()
    if s.sentry_dsn:
        sentry_sdk.init(
            dsn=s.sentry_dsn,
            environment=s.env,
            traces_sample_rate=0.05,
            send_default_pii=False,
        )


def instrument(app):  # type: ignore[no-untyped-def]
    return Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics", "/healthz", "/readyz"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


log = structlog.get_logger()
