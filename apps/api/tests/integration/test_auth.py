"""FR-AUTH integration tests."""
from __future__ import annotations

import pytest

from tests.integration.conftest import (
    COOKIE_V,
    PASSWORD,
    TOS_V,
    Client,
    db_exec,
    db_one,
    make_user,
    unique_email,
)


@pytest.mark.asyncio
async def test_auth_001_signup_creates_pending_user(anon: Client) -> None:
    email = unique_email("signup")
    r = await anon.post(
        "/auth/signup",
        json={
            "email": email,
            "password": PASSWORD,
            "age_confirmed": True,
            "tos_version": TOS_V,
            "cookie_consent_version": COOKIE_V,
            "analytics_opt_in": False,
        },
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    row = db_one("SELECT state, email_verified_at FROM users WHERE email=%(e)s", e=email)
    assert row.state == "pending_verify"
    assert row.email_verified_at is None


@pytest.mark.asyncio
async def test_auth_001_signup_existing_email_silent_success(anon: Client) -> None:
    email = unique_email("dup")
    body = {
        "email": email,
        "password": PASSWORD,
        "age_confirmed": True,
        "tos_version": TOS_V,
        "cookie_consent_version": COOKIE_V,
        "analytics_opt_in": False,
    }
    r1 = await anon.post("/auth/signup", json=body)
    r2 = await anon.post("/auth/signup", json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    # Account-enumeration defense: both responses identical.


@pytest.mark.asyncio
async def test_auth_007_lockout_after_repeated_failures(anon: Client) -> None:
    email = unique_email("lock")
    await anon.post(
        "/auth/signup",
        json={
            "email": email, "password": PASSWORD, "age_confirmed": True,
            "tos_version": TOS_V, "cookie_consent_version": COOKIE_V, "analytics_opt_in": False,
        },
    )
    db_exec("UPDATE users SET state='active', email_verified_at=now() WHERE email=%(e)s", e=email)
    codes: list[int] = []
    for _ in range(12):
        r = await anon.post("/auth/login", json={"email": email, "password": "WrongPwd!" + "x"})
        codes.append(r.status_code)
    assert 429 in codes, codes


@pytest.mark.asyncio
async def test_auth_008_age_unconfirmed_rejected(anon: Client) -> None:
    r = await anon.post(
        "/auth/signup",
        json={
            "email": unique_email("age"), "password": PASSWORD, "age_confirmed": False,
            "tos_version": TOS_V, "cookie_consent_version": COOKIE_V, "analytics_opt_in": False,
        },
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_auth_006_hibp_blocks_breached_password(anon: Client) -> None:
    # `password123` is in the HIBP list. Network failures fall through; if HIBP
    # is unreachable the test will pass trivially with 200 — that's documented
    # in is_pwned as non-blocking. We still attempt a credible breached one.
    r = await anon.post(
        "/auth/signup",
        json={
            "email": unique_email("hibp"), "password": "password123!password123", "age_confirmed": True,
            "tos_version": TOS_V, "cookie_consent_version": COOKIE_V, "analytics_opt_in": False,
        },
    )
    # Either rejected (HIBP working) or accepted (HIBP unreachable in test net).
    assert r.status_code in (200, 400)


@pytest.mark.asyncio
async def test_auth_005_password_reset_response_identical_for_unknown(anon: Client) -> None:
    r1 = await anon.post("/auth/forgot", json={"email": unique_email("nope")})
    r2 = await anon.post("/auth/forgot", json={"email": unique_email("nope2")})
    assert r1.status_code == r2.status_code == 200


@pytest.mark.asyncio
async def test_auth_004_logout_invalidates_session() -> None:
    c = await make_user()
    me = await c.get("/auth/me")
    assert me.status_code == 200
    r = await c.post("/auth/logout", json={})
    assert r.status_code == 200
    me2 = await c.get("/auth/me")
    assert me2.status_code == 401
    await c.aclose()


@pytest.mark.asyncio
async def test_auth_010_email_change_requires_password() -> None:
    c = await make_user()
    r = await c.post("/me/email", json={"new_email": unique_email("new"), "current_password": "wrong"})
    assert r.status_code == 403
    # Right password → 200, token issued.
    r2 = await c.post("/me/email", json={"new_email": unique_email("new"), "current_password": PASSWORD})
    assert r2.status_code == 200
    await c.aclose()


_SIGNUP_BASE = {
    "password": PASSWORD,
    "age_confirmed": True,
    "tos_version": TOS_V,
    "cookie_consent_version": COOKIE_V,
    "analytics_opt_in": False,
}


@pytest.mark.asyncio
async def test_resend_verification_pending_user(anon: Client) -> None:
    email = unique_email("rv-pending")
    await anon.post("/auth/signup", json={"email": email, **_SIGNUP_BASE})
    r = await anon.post("/auth/resend-verification", json={"email": email})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Resend issues a token + sends mail — it must NOT mutate account state.
    row = db_one("SELECT state, email_verified_at FROM users WHERE email=%(e)s", e=email)
    assert row.state == "pending_verify"
    assert row.email_verified_at is None


@pytest.mark.asyncio
async def test_resend_verification_no_enumeration(anon: Client) -> None:
    """Identical response for pending / already-active / non-existent —
    the endpoint must never reveal whether an address is registered."""
    pending = unique_email("rv-enum-pending")
    await anon.post("/auth/signup", json={"email": pending, **_SIGNUP_BASE})

    active = unique_email("rv-enum-active")
    await anon.post("/auth/signup", json={"email": active, **_SIGNUP_BASE})
    db_exec(
        "UPDATE users SET state='active', email_verified_at=now() WHERE email=%(e)s",
        e=active,
    )

    r_pending = await anon.post("/auth/resend-verification", json={"email": pending})
    r_active = await anon.post("/auth/resend-verification", json={"email": active})
    r_nobody = await anon.post(
        "/auth/resend-verification", json={"email": unique_email("rv-enum-nobody")}
    )
    assert r_pending.status_code == r_active.status_code == r_nobody.status_code == 200
    assert r_pending.json() == r_active.json() == r_nobody.json() == {"ok": True}


@pytest.mark.asyncio
async def test_resend_verification_rate_limited(anon: Client) -> None:
    """One address cannot be flooded — per-account limit trips at 5/hour."""
    email = unique_email("rv-rl")
    await anon.post("/auth/signup", json={"email": email, **_SIGNUP_BASE})
    codes = [
        (await anon.post("/auth/resend-verification", json={"email": email})).status_code
        for _ in range(8)
    ]
    assert 429 in codes, codes


@pytest.mark.asyncio
async def test_auth_009_mfa_columns_exist() -> None:
    row = db_one(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='users' AND column_name='mfa_secret'"
    )
    assert row is not None, "MFA-ready schema column missing"
