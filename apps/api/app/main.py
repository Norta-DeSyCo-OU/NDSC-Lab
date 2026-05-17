"""FastAPI app entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin.queue import router as admin_queue_router
from app.admin.routes import router as admin_router
from app.analytics.routes import router as analytics_router
from app.certification.routes import router as cert_router
from app.comments.routes import router as comments_router
from app.content.admin_routes import router as content_admin_router
from app.content.routes import router as content_router
from app.content.uploads import router as uploads_router
from app.core.redis_client import get_redis
from app.core.security.csrf import issue_csrf
from app.core.settings import get_settings
from app.core.telemetry import configure_logging, init_sentry, instrument, log
from app.curation.routes import router as curation_router
from app.identity.contributor_routes import router as contrib_router
from app.identity.oauth_routes import router as oauth_router
from app.identity.routes import router as identity_router
from app.identity.self_routes import router as self_router
from app.legal.routes import router as legal_router


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    configure_logging()
    init_sentry()
    r = await get_redis()
    try:
        await r.ping()
    except Exception as e:  # noqa: BLE001
        log.warning("redis_unreachable_at_startup", error=str(e))
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="NDSC Lab API",
        version="0.1.0",
        docs_url="/docs" if s.env != "prod" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "interest-cohort=()"
        if s.env == "prod":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response

    # Defense-in-depth: enforce CSRF *before* body parsing for any state-changing
    # request. Carve-out paths use their own checks (login/signup require csrf
    # cookie but are bootstrap-friendly; the `/csrf` endpoint issues the cookie).
    # Public verification accepts third-party PDF uploads with no prior session —
    # exempt from CSRF (no state mutation, no authenticated context).
    _CSRF_EXEMPT_PATHS: set[str] = set()
    _CSRF_EXEMPT_PREFIXES: tuple[str, ...] = ("/verify/",)
    _MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    import hmac as _hmac

    @app.middleware("http")
    async def csrf_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method in _MUTATING_METHODS:
            path = request.url.path
            if path not in _CSRF_EXEMPT_PATHS and not any(
                path.startswith(p) for p in _CSRF_EXEMPT_PREFIXES
            ):
                cookie = request.cookies.get(s.csrf_cookie_name)
                header = request.headers.get("X-CSRF-Token")
                if not cookie or not header or not _hmac.compare_digest(cookie, header):
                    from fastapi.responses import JSONResponse as _JR
                    return _JR({"detail": "csrf_failed"}, status_code=403)
        return await call_next(request)

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/readyz")
    async def readyz() -> dict[str, Any]:
        r = await get_redis()
        await r.ping()
        return {"ok": True}

    @app.get("/csrf")
    async def csrf_endpoint():  # noqa: ANN201
        resp = JSONResponse({"ok": True})
        issue_csrf(resp)
        return resp

    app.include_router(identity_router)
    app.include_router(oauth_router)
    app.include_router(contrib_router)
    app.include_router(self_router)
    app.include_router(content_router)
    app.include_router(content_admin_router)
    app.include_router(uploads_router)
    app.include_router(curation_router)
    app.include_router(comments_router)
    app.include_router(analytics_router)
    app.include_router(cert_router)
    app.include_router(admin_router)
    app.include_router(admin_queue_router)
    app.include_router(legal_router)

    instrument(app)
    return app


app = create_app()
