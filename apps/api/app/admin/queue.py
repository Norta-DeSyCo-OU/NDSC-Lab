"""Admin queue/listing endpoints (users, items pending review, applications, takedowns, certs)."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.certification.models import Certificate
from app.comments.models import CommentReport
from app.content.models import Item, ReviewSubmission
from app.core.db import get_session
from app.core.policy import Actor
from app.curation.models import CertCompletionSuggestion, Collection
from app.identity.deps import require_admin
from app.identity.models import ContributorApplication, User
from app.legal.models import TakedownRequest

router = APIRouter(prefix="/admin", tags=["admin"])


# ----- counts ---------------------------------------------------------------


class CountsOut(BaseModel):
    pending_review_items: int
    pending_applications: int
    open_takedowns: int
    open_comment_reports: int
    open_cert_suggestions: int


@router.get("/queue/counts", response_model=CountsOut)
async def queue_counts(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> CountsOut:
    pri = await s.scalar(select(func.count("*")).where(Item.state == "pending_review"))
    pa = await s.scalar(
        select(func.count("*")).where(ContributorApplication.state == "pending")
    )
    ot = await s.scalar(select(func.count("*")).where(TakedownRequest.state == "open"))
    ocr = await s.scalar(select(func.count("*")).where(CommentReport.state == "open"))
    ocs = await s.scalar(
        select(func.count("*")).where(CertCompletionSuggestion.state == "open")
    )
    return CountsOut(
        pending_review_items=int(pri or 0),
        pending_applications=int(pa or 0),
        open_takedowns=int(ot or 0),
        open_comment_reports=int(ocr or 0),
        open_cert_suggestions=int(ocs or 0),
    )


# ----- users ---------------------------------------------------------------


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    state: str
    display_name: str | None
    created_at: datetime


@router.get("/users", response_model=list[UserOut])
async def list_users(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = None,
    role: Literal["user", "contributor", "admin"] | None = None,
    state: Literal["pending_verify", "active", "banned", "deleted"] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[UserOut]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(User.email.ilike(like), User.display_name.ilike(like)))
    if role:
        conds.append(User.role == role)
    if state:
        conds.append(User.state == state)
    stmt = (
        select(User)
        .where(and_(*conds) if conds else True)
        .order_by(desc(User.created_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await s.scalars(stmt)).all()
    return [
        UserOut(
            id=u.id,
            email=u.email,
            role=u.role,
            state=u.state,
            display_name=u.display_name,
            created_at=u.created_at,
        )
        for u in rows
    ]


# ----- items pending review -------------------------------------------------


class ReviewItemOut(BaseModel):
    id: str
    title: str
    author_id: str
    author_email: str
    type: str
    submitted_at: datetime | None


@router.get("/items/pending", response_model=list[ReviewItemOut])
async def list_pending(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
    offset: int = 0,
) -> list[ReviewItemOut]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    stmt = (
        select(Item, User.email, ReviewSubmission.created_at)
        .join(User, User.id == Item.author_id)
        .outerjoin(
            ReviewSubmission,
            (ReviewSubmission.item_id == Item.id) & (ReviewSubmission.state == "pending"),
        )
        .where(Item.state == "pending_review")
        .order_by(desc(Item.updated_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await s.execute(stmt)).all()
    return [
        ReviewItemOut(
            id=row[0].id,
            title=row[0].title,
            author_id=row[0].author_id,
            author_email=row[1],
            type=row[0].type,
            submitted_at=row[2],
        )
        for row in rows
    ]


# ----- generic items browse (moderation) -----------------------------------


class ItemBrowseOut(BaseModel):
    id: str
    title: str
    type: str
    state: str
    author_id: str
    author_email: str
    summary: str | None
    published_at: datetime | None
    updated_at: datetime
    created_at: datetime


@router.get("/items", response_model=list[ItemBrowseOut])
async def list_items_admin(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    state: Literal["draft", "pending_review", "published", "tombstoned"] | None = None,
    q: str | None = None,
    author: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ItemBrowseOut]:
    """List items for admin moderation. Default excludes tombstoned."""
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    conds = []
    if state:
        conds.append(Item.state == state)
    else:
        conds.append(Item.state != "tombstoned")
    if author:
        conds.append(Item.author_id == author)
    if q:
        like = f"%{q}%"
        conds.append(or_(Item.title.ilike(like), Item.summary.ilike(like)))
    stmt = (
        select(Item, User.email)
        .join(User, User.id == Item.author_id)
        .where(and_(*conds))
        .order_by(desc(Item.updated_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await s.execute(stmt)).all()
    return [
        ItemBrowseOut(
            id=row[0].id,
            title=row[0].title,
            type=row[0].type,
            state=row[0].state,
            author_id=row[0].author_id,
            author_email=row[1],
            summary=row[0].summary,
            published_at=row[0].published_at,
            updated_at=row[0].updated_at,
            created_at=row[0].created_at,
        )
        for row in rows
    ]


# ----- contributor applications --------------------------------------------


class ApplicationOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    motivation: str
    links: dict | None
    state: str
    created_at: datetime


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    state: Literal["pending", "approved", "rejected", "withdrawn"] | None = "pending",
    limit: int = 50,
    offset: int = 0,
) -> list[ApplicationOut]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    stmt = (
        select(ContributorApplication, User.email)
        .join(User, User.id == ContributorApplication.user_id)
        .order_by(desc(ContributorApplication.created_at))
        .limit(limit)
        .offset(offset)
    )
    if state:
        stmt = stmt.where(ContributorApplication.state == state)
    rows = (await s.execute(stmt)).all()
    return [
        ApplicationOut(
            id=row[0].id,
            user_id=row[0].user_id,
            user_email=row[1],
            motivation=row[0].motivation,
            links=row[0].links,
            state=row[0].state,
            created_at=row[0].created_at,
        )
        for row in rows
    ]


# ----- takedowns ------------------------------------------------------------


class TakedownOut(BaseModel):
    id: str
    complainant_name: str
    complainant_email: str
    target_url: str
    sworn_statement: str
    state: str
    created_at: datetime


@router.get("/takedowns", response_model=list[TakedownOut])
async def list_takedowns(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    state: Literal["open", "closed_tombstoned", "closed_rejected"] | None = "open",
    limit: int = 50,
    offset: int = 0,
) -> list[TakedownOut]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    stmt = (
        select(TakedownRequest)
        .order_by(desc(TakedownRequest.created_at))
        .limit(limit)
        .offset(offset)
    )
    if state:
        stmt = stmt.where(TakedownRequest.state == state)
    rows = (await s.scalars(stmt)).all()
    return [
        TakedownOut(
            id=t.id,
            complainant_name=t.complainant_name,
            complainant_email=t.complainant_email,
            target_url=t.target_url,
            sworn_statement=t.sworn_statement,
            state=t.state,
            created_at=t.created_at,
        )
        for t in rows
    ]


# ----- certificates ---------------------------------------------------------


class CertListOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    collection_id: str
    collection_title: str | None
    issued_at: datetime
    revoked_at: datetime | None


@router.get("/certificates", response_model=list[CertListOut])
async def list_certificates(
    actor: Annotated[Actor, Depends(require_admin)],
    s: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
    offset: int = 0,
) -> list[CertListOut]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)
    stmt = (
        select(Certificate, User.email, Collection.title)
        .join(User, User.id == Certificate.user_id)
        .outerjoin(Collection, Collection.id == Certificate.collection_id)
        .order_by(desc(Certificate.issued_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await s.execute(stmt)).all()
    return [
        CertListOut(
            id=row[0].id,
            user_id=row[0].user_id,
            user_email=row[1],
            collection_id=row[0].collection_id,
            collection_title=row[2],
            issued_at=row[0].issued_at,
            revoked_at=row[0].revoked_at,
        )
        for row in rows
    ]
