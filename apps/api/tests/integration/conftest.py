"""Integration test scaffolding.

Talks to the running api at http://localhost:8000 from inside the api container.
Uses synchronous psycopg2 for DB access to sidestep asyncpg/event-loop coupling
issues with pytest-asyncio.
"""
from __future__ import annotations

import os
import uuid
from typing import Iterator

import httpx
import psycopg2
import psycopg2.extras
import pytest
import pytest_asyncio
import redis as _redis_lib

# Bootstrap env vars (mirror app/settings expectations).
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql+asyncpg://ndsc:ndsc@db:5432/ndsc"))
os.environ.setdefault("REDIS_URL", os.environ.get("REDIS_URL", "redis://redis:6379/0"))

BASE = os.environ.get("API_BASE", "http://localhost:8000")
TOS_V = "2026-05-13"
COOKIE_V = "2026-05-13"
PASSWORD = "AutomatedTestPwd12345!"

# Build a sync DSN from the asyncpg DSN.
_DB = os.environ["DATABASE_URL"].replace("+asyncpg", "")


def _pg():
    return psycopg2.connect(_DB)


def db_exec(sql: str, **params) -> None:
    with _pg() as c, c.cursor() as cur:
        cur.execute(sql, params)


def db_one(sql: str, **params):
    with _pg() as c, c.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


_TRUNCATE_SQL = (
    "TRUNCATE users, items, audit_log, oauth_identities, login_attempts, "
    "tos_acceptances, cookie_consents, contributor_profiles, certificates, "
    "signing_keys, collections, cert_admin_pseudonyms, attachments, "
    "collection_items, comments, comment_reports, contributor_applications, "
    "role_transitions, takedown_requests, erasure_requests, data_export_requests, "
    "platform_settings, workshops, workshop_speakers, raw_view_events, "
    "daily_item_aggregates, daily_contributor_aggregates "
    "CASCADE"
)


@pytest.fixture(scope="session", autouse=True)
def _clean_state_session():
    with _pg() as c, c.cursor() as cur:
        cur.execute(_TRUNCATE_SQL)
    _redis_lib.from_url(os.environ["REDIS_URL"]).flushdb()
    yield


@pytest.fixture(autouse=True)
def _clean_state_per_test():
    # Reset rate limits + sessions + DB between tests so order-of-execution
    # doesn't matter and lockouts from one test don't poison the next.
    _redis_lib.from_url(os.environ["REDIS_URL"]).flushdb()
    with _pg() as c, c.cursor() as cur:
        cur.execute(_TRUNCATE_SQL)
    yield


def unique_email(prefix: str = "u") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


class Client:
    def __init__(self, email: str, role: str = "user"):
        self.email = email
        self.role = role
        self.http = httpx.AsyncClient(base_url=BASE, timeout=15.0, follow_redirects=False)
        self._csrf: str | None = None

    async def aclose(self):
        await self.http.aclose()

    async def _ensure_csrf(self) -> str:
        # Always use the most recent cookie value — server may rotate the CSRF
        # cookie on every state-changing response, and we need the new value to
        # match the cookie on the next request.
        tok = self.http.cookies.get("ndsc_csrf")
        if not tok:
            r = await self.http.get("/csrf")
            r.raise_for_status()
            tok = self.http.cookies.get("ndsc_csrf")
        assert tok, "csrf cookie missing"
        return tok

    async def get(self, path: str, **kw):
        return await self.http.get(path, **kw)

    async def post(self, path: str, json: dict | None = None, **kw):
        tok = await self._ensure_csrf()
        headers = kw.pop("headers", {}) or {}
        headers["X-CSRF-Token"] = tok
        return await self.http.post(path, json=json, headers=headers, **kw)

    async def put(self, path: str, json: dict | None = None, **kw):
        tok = await self._ensure_csrf()
        headers = kw.pop("headers", {}) or {}
        headers["X-CSRF-Token"] = tok
        return await self.http.put(path, json=json, headers=headers, **kw)

    async def patch(self, path: str, json: dict | None = None, **kw):
        tok = await self._ensure_csrf()
        headers = kw.pop("headers", {}) or {}
        headers["X-CSRF-Token"] = tok
        return await self.http.patch(path, json=json, headers=headers, **kw)

    async def delete(self, path: str, **kw):
        tok = await self._ensure_csrf()
        headers = kw.pop("headers", {}) or {}
        headers["X-CSRF-Token"] = tok
        return await self.http.delete(path, headers=headers, **kw)

    async def upload_simple(self, path: str, *, item_id: str, role: str, filename: str, mime: str, body: bytes):
        tok = await self._ensure_csrf()
        files = {"file": (filename, body, mime)}
        data = {"item_id": item_id, "role": role}
        return await self.http.post(
            path, files=files, data=data, headers={"X-CSRF-Token": tok}
        )


async def make_user(email: str | None = None, *, role: str = "user", verified: bool = True) -> Client:
    email = email or unique_email()
    c = Client(email, role=role)
    r = await c.post(
        "/auth/signup",
        json={
            "email": email,
            "password": PASSWORD,
            "age_confirmed": True,
            "tos_version": TOS_V,
            "cookie_consent_version": COOKIE_V,
            "analytics_opt_in": True,
        },
    )
    assert r.status_code == 200, r.text

    if verified or role != "user":
        db_exec(
            "UPDATE users SET state='active', email_verified_at=now(), role=%(r)s WHERE email=%(e)s",
            r=role, e=email,
        )

    r = await c.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return c


@pytest_asyncio.fixture
async def user() -> Iterator[Client]:
    c = await make_user(role="user")
    try:
        yield c
    finally:
        await c.aclose()


@pytest_asyncio.fixture
async def contributor() -> Iterator[Client]:
    c = await make_user(role="contributor")
    try:
        yield c
    finally:
        await c.aclose()


@pytest_asyncio.fixture
async def admin() -> Iterator[Client]:
    c = await make_user(role="admin")
    try:
        yield c
    finally:
        await c.aclose()


@pytest_asyncio.fixture
async def anon() -> Iterator[Client]:
    c = Client("anon")
    try:
        yield c
    finally:
        await c.aclose()
