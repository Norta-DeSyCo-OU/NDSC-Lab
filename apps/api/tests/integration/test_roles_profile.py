"""FR-ROLE + FR-PROFILE integration tests."""
from __future__ import annotations

import pytest

from tests.integration.conftest import Client, db_one, make_user, unique_email


@pytest.mark.asyncio
async def test_role_002_user_can_apply_to_be_contributor(user: Client) -> None:
    r = await user.post(
        "/me/contributor-application",
        json={"motivation": "I want to publish lectures on ZKP and MAS." * 1, "links": {"site": "https://x"}},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["state"] == "pending"


@pytest.mark.asyncio
async def test_role_003_admin_approves_application(admin: Client) -> None:
    # Create a separate user + application.
    u = await make_user()
    await u.post(
        "/me/contributor-application",
        json={"motivation": "twenty characters minimum to satisfy validation", "links": {}},
    )
    apps = (await admin.get("/admin/applications?state=pending")).json()
    target = next(a for a in apps if a["user_id"])
    r = await admin.post(f"/admin/applications/{target['id']}/decide", json={"approve": True, "reason": "ok"})
    assert r.status_code == 200
    row = db_one("SELECT role FROM users WHERE id=%(id)s", id=target["user_id"])
    assert row.role == "contributor"
    await u.aclose()


@pytest.mark.asyncio
async def test_role_004_admin_can_change_role_directly(admin: Client) -> None:
    u = await make_user()
    me = (await u.get("/auth/me")).json()
    r = await admin.post(f"/admin/users/{me['id']}/role", json={"role": "contributor"})
    assert r.status_code == 200
    row = db_one("SELECT role FROM users WHERE id=%(id)s", id=me["id"])
    assert row.role == "contributor"
    await u.aclose()


@pytest.mark.asyncio
async def test_role_005_contributor_can_self_revoke() -> None:
    c = await make_user(role="contributor")
    r = await c.post("/me/contributor/revoke", json={"confirm": True, "content_fate": "tombstone"})
    assert r.status_code == 200, r.text
    me_row = db_one("SELECT role FROM users WHERE email=%(e)s", e=c.email)
    assert me_row.role == "user"
    await c.aclose()


@pytest.mark.asyncio
async def test_role_006_admin_can_ban(admin: Client) -> None:
    u = await make_user()
    me = (await u.get("/auth/me")).json()
    r = await admin.post(f"/admin/users/{me['id']}/ban", json={"reason": "test"})
    assert r.status_code == 200
    row = db_one("SELECT state FROM users WHERE id=%(id)s", id=me["id"])
    assert row.state == "banned"
    await u.aclose()


@pytest.mark.asyncio
async def test_profile_001_002_contributor_can_set_profile(contributor: Client) -> None:
    r = await contributor.put(
        "/me/profile",
        json={
            "slug": "alice-" + unique_email("p").split("@")[0],
            "bio_md": "**Hello** world",
            "affiliation": "Norta DeSyCo OU",
            "orcid": "0000-0001-2345-6789",
            "links": [{"label": "Site", "url": "https://example.com/"}],
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["slug"].startswith("alice-")
    # Public page renders.
    pub = await contributor.get(f"/c/{out['slug']}")
    assert pub.status_code == 200


@pytest.mark.asyncio
async def test_profile_003_reserved_slug_suffixed(contributor: Client) -> None:
    r = await contributor.put("/me/profile", json={"slug": "admin"})
    assert r.status_code == 200
    out = r.json()
    assert out["slug"] != "admin"
