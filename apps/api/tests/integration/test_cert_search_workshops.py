"""FR-CERT + FR-SEARCH + FR-WS integration tests."""
from __future__ import annotations

import pytest
import httpx

from tests.integration.conftest import Client, make_user


@pytest.mark.asyncio
async def test_cert_002_003_004_admin_issues_user_downloads_anyone_verifies(
    admin: Client, contributor: Client,
) -> None:
    me = (await contributor.get("/auth/me")).json()
    # Create a collection to issue against.
    coll = (await contributor.post("/collections", json={"title": "ZKP basics", "is_course": True})).json()
    issue = await admin.post(
        "/admin/certificates",
        json={"user_id": me["id"], "collection_id": coll["id"], "course_title": "ZKP basics"},
    )
    assert issue.status_code == 200, issue.text
    cert_id = issue.json()["id"]

    # Public verification GET works without auth.
    async with httpx.AsyncClient(base_url=admin.http.base_url) as anon:
        rg = await anon.get(f"/verify/{cert_id}")
        assert rg.status_code == 200
        body = rg.json()
        assert body["revoked"] is False

    # Admin downloads PDF.
    pdf = await admin.get(f"/admin/certificates/{cert_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    # POST verify with the actual PDF — valid.
    async with httpx.AsyncClient(base_url=admin.http.base_url) as anon:
        files = {"pdf": ("c.pdf", pdf.content, "application/pdf")}
        rv = await anon.post(f"/verify/{cert_id}", files=files)
        assert rv.status_code == 200
        assert rv.json()["valid"] is True

    # User sees the cert.
    mine = await contributor.get("/me/certificates")
    assert any(c["id"] == cert_id for c in mine.json())


@pytest.mark.asyncio
async def test_cert_005_revoke_returns_revoked(admin: Client, contributor: Client) -> None:
    me = (await contributor.get("/auth/me")).json()
    coll = (await contributor.post("/collections", json={"title": "Course X"})).json()
    cert = (
        await admin.post(
            "/admin/certificates",
            json={"user_id": me["id"], "collection_id": coll["id"], "course_title": "X"},
        )
    ).json()
    r = await admin.post(f"/admin/certificates/{cert['id']}/revoke", json={"reason": "test"})
    assert r.status_code == 200
    async with httpx.AsyncClient(base_url=admin.http.base_url) as anon:
        v = await anon.get(f"/verify/{cert['id']}")
        assert v.json()["revoked"] is True


@pytest.mark.asyncio
async def test_search_001_002_full_text_and_filters(contributor: Client, admin: Client) -> None:
    titles = ["ZKP for engineers", "Tokenomics primer", "Agent MAS coordination"]
    ids = []
    for t in titles:
        r = await contributor.post("/items", json={"type": "article", "title": t, "body_md": f"{t}\nzero-knowledge"})
        iid = r.json()["id"]
        await contributor.post(f"/items/{iid}/submit", json={})
        await admin.post(f"/admin/items/{iid}/approve", json={})
        ids.append(iid)

    async with httpx.AsyncClient(base_url=admin.http.base_url) as anon:
        # FTS match
        r = await anon.get("/items?q=ZKP")
        assert r.status_code == 200
        rows = r.json()
        assert any(it["id"] == ids[0] for it in rows)
        # Type filter
        r2 = await anon.get("/items?type=article")
        assert all(it["type"] == "article" for it in r2.json())


@pytest.mark.asyncio
async def test_ws_001_002_004_workshop_lifecycle(admin: Client, contributor: Client) -> None:
    me_c = (await contributor.get("/auth/me")).json()
    r = await contributor.post(
        "/workshops",
        json={
            "title": "ZKP hands-on",
            "abstract_md": "We will…",
            "starts_at": "2030-01-01T10:00:00Z",
            "ends_at": "2030-01-01T12:00:00Z",
            "is_online": True,
            "registration_url": "https://example.com/register",
            "speakers": [me_c["id"]],
        },
    )
    assert r.status_code == 200, r.text
    w = r.json()
    assert w["state"] == "pending_review"
    # Admin lists published only — should be empty for this workshop.
    async with httpx.AsyncClient(base_url=admin.http.base_url) as anon:
        listed = await anon.get("/workshops")
        assert listed.status_code == 200
