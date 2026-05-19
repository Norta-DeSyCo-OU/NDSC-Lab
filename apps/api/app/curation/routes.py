"""Curation routes: profiles, collections, courses, workshops."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.models import Attachment
from app.content.slug import is_reserved, normalize_slug
from app.core.audit import record as audit_record
from app.core.db import get_session
from app.core.policy import Actor
from app.core.security.csrf import require_csrf
from app.curation.models import (
    Collection,
    CollectionItem,
    ContributorProfile,
    ProfileSection,
    Workshop,
    WorkshopSpeaker,
)
from app.identity.deps import current_actor, require_user
from app.identity.models import User

router = APIRouter(tags=["curation"])


# -- Profile -----------------------------------------------------------------

class ProfileLink(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    url: HttpUrl


class ProfileContact(BaseModel):
    kind: str = Field(pattern=r"^(email|phone)$")
    value: str = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=64)


class ProfileIn(BaseModel):
    slug: str | None = None
    bio_md: str | None = Field(default=None, max_length=8000)
    affiliation: str | None = Field(default=None, max_length=200)
    orcid: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
    links: list[ProfileLink] | None = None
    contacts: list[ProfileContact] | None = None


class ProfileOut(BaseModel):
    user_id: str
    slug: str
    bio_md: str | None
    affiliation: str | None
    orcid: str | None
    links: list[dict[str, Any]] | None
    contacts: list[dict[str, Any]] | None = None
    photo_url: str | None = None


def _photo_url_for(profile: ContributorProfile) -> str | None:
    return f"/api/c/photo/{profile.user_id}" if profile.photo_attachment_id else None


async def _get_or_create_profile(
    s: AsyncSession, user_id: str, slug_hint: str | None = None
) -> ContributorProfile:
    """Return the actor's profile row, creating it lazily on first use.

    Mirrors the slug-allocation logic of `upsert_profile` so any endpoint
    that needs a profile (photo upload, sections…) can be invoked before
    the user has ever pressed "Save" on the profile form.
    """
    profile = await s.scalar(
        select(ContributorProfile).where(ContributorProfile.user_id == user_id)
    )
    if profile:
        return profile
    slug = normalize_slug(slug_hint or user_id or "user")
    if is_reserved(slug):
        slug = f"{slug}-c"
    base = slug
    n = 0
    while await s.scalar(select(ContributorProfile).where(ContributorProfile.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    profile = ContributorProfile(user_id=user_id, slug=slug)  # type: ignore[arg-type]
    s.add(profile)
    await s.flush()
    return profile


@router.put("/me/profile", response_model=ProfileOut)
async def upsert_profile(
    body: ProfileIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileOut:
    require_csrf(request)
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="contributor_required")

    existed = await s.scalar(
        select(ContributorProfile).where(ContributorProfile.user_id == actor.user_id)
    )
    if not existed:
        profile = await _get_or_create_profile(s, actor.user_id, slug_hint=body.slug)  # type: ignore[arg-type]
    else:
        profile = existed
    if existed and body.slug:
        new_slug = normalize_slug(body.slug)
        if new_slug != profile.slug and not is_reserved(new_slug):
            taken = await s.scalar(select(ContributorProfile).where(ContributorProfile.slug == new_slug))
            if not taken:
                profile.slug = new_slug

    if body.bio_md is not None:
        profile.bio_md = body.bio_md
    if body.affiliation is not None:
        profile.affiliation = body.affiliation
    if body.orcid is not None:
        profile.orcid = body.orcid
    if body.links is not None:
        profile.links = [{"label": ln.label, "url": str(ln.url)} for ln in body.links]
    if body.contacts is not None:
        profile.contacts = [
            {"kind": c.kind, "value": c.value, "label": c.label} for c in body.contacts
        ]

    return ProfileOut(
        user_id=profile.user_id,
        slug=profile.slug,
        bio_md=profile.bio_md,
        affiliation=profile.affiliation,
        orcid=profile.orcid,
        links=profile.links,
        contacts=profile.contacts,
        photo_url=_photo_url_for(profile),
    )


@router.get("/c/{slug}", response_model=ProfileOut)
async def get_profile(
    slug: str,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileOut:
    profile = await s.scalar(select(ContributorProfile).where(ContributorProfile.slug == slug))
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    user = await s.scalar(select(User).where(User.id == profile.user_id))
    if not user or user.state != "active" or user.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return ProfileOut(
        user_id=profile.user_id,
        slug=profile.slug,
        bio_md=profile.bio_md,
        affiliation=profile.affiliation,
        orcid=profile.orcid,
        links=profile.links,
        contacts=profile.contacts,
        photo_url=_photo_url_for(profile),
    )


# -- Profile photo ----------------------------------------------------------

ALLOWED_PHOTO_MIME = {"image/png", "image/jpeg", "image/webp"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB cap — profile photos


@router.post("/me/profile/photo")
async def upload_profile_photo(
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Upload (or replace) the contributor's profile photo. Inline scan."""
    require_csrf(request)
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="contributor_required")

    import aioboto3  # type: ignore

    from app.core.settings import get_settings

    settings = get_settings()

    mime = file.content_type or "application/octet-stream"
    # Fallback for browsers that report octet-stream — sniff filename ext.
    if mime not in ALLOWED_PHOTO_MIME:
        ext = ""
        if file.filename and "." in file.filename:
            ext = "." + file.filename.rsplit(".", 1)[1].lower()
        ext_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        guess = ext_map.get(ext)
        if guess:
            mime = guess
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="mime_not_allowed")

    body = await file.read(MAX_PHOTO_BYTES + 1)
    if len(body) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="photo_too_large")

    # Look up — but do NOT create — the profile row yet, so a failed
    # ClamAV/R2 upload never leaves an empty profile in the public directory.
    profile = await s.scalar(
        select(ContributorProfile).where(ContributorProfile.user_id == actor.user_id)
    )

    # Optional ClamAV scan inline — fast for ≤5 MB.
    try:
        import pyclamd  # type: ignore[import-untyped]

        cd = pyclamd.ClamdNetworkSocket(host=settings.clamav_host, port=settings.clamav_port)
        if cd.ping():
            result = cd.scan_stream(body)
            if result is not None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="photo_infected")
    except HTTPException:
        raise
    except Exception:
        pass

    import re as _re
    import secrets as _secrets

    safe_name = _re.sub(r"[^A-Za-z0-9._-]+", "_", file.filename or "avatar")[:120]
    # Include a random prefix so re-uploads never collide with the unique
    # `attachments.r2_key` index, and old photos can be garbage-collected at
    # leisure rather than overwriting in place.
    r2_key = f"users/{actor.user_id}/profile_photo/{_secrets.token_hex(4)}_{safe_name}"

    sess = aioboto3.Session()
    s3_kwargs = {
        "endpoint_url": settings.r2_endpoint_url,
        "region_name": settings.r2_region,
        "aws_access_key_id": settings.r2_access_key_id.get_secret_value(),
        "aws_secret_access_key": settings.r2_secret_access_key.get_secret_value(),
    }

    # Drop the previous photo's R2 object + attachment row (best-effort).
    old_att_id = profile.photo_attachment_id if profile else None
    if old_att_id and profile:
        old_att = await s.scalar(select(Attachment).where(Attachment.id == old_att_id))
        if old_att:
            try:
                async with sess.client("s3", **s3_kwargs) as c:
                    await c.delete_object(Bucket=settings.r2_hot_bucket, Key=old_att.r2_key)
            except Exception:
                # R2 delete failed — proceed; orphan object is harmless.
                pass
            profile.photo_attachment_id = None
            await s.flush()
            await s.delete(old_att)
            await s.flush()

    async with sess.client("s3", **s3_kwargs) as c:
        await c.put_object(
            Bucket=settings.r2_hot_bucket, Key=r2_key, Body=body, ContentType=mime
        )

    # R2 put succeeded — only now lazily create the profile row if missing.
    if not profile:
        profile = await _get_or_create_profile(s, actor.user_id)  # type: ignore[arg-type]

    att = Attachment(
        owner_user_id=actor.user_id,  # type: ignore[arg-type]
        item_id=None,
        role="profile_photo",
        r2_key=r2_key,
        bytes=len(body),
        mime=mime,
        state="clean",
    )
    s.add(att)
    await s.flush()
    profile.photo_attachment_id = att.id
    return {"photo_url": f"/api/c/photo/{profile.user_id}"}


@router.delete("/me/profile/photo")
async def delete_profile_photo(
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="contributor_required")
    profile = await s.scalar(
        select(ContributorProfile).where(ContributorProfile.user_id == actor.user_id)
    )
    if not profile or not profile.photo_attachment_id:
        return {"ok": "no_photo"}
    profile.photo_attachment_id = None
    return {"ok": "deleted"}


@router.get("/c/photo/{user_id}")
async def stream_profile_photo(
    user_id: str,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    """Public photo stream for the contributor's avatar."""
    import aioboto3  # type: ignore

    from app.core.settings import get_settings

    profile = await s.scalar(
        select(ContributorProfile).where(ContributorProfile.user_id == user_id)
    )
    if not profile or not profile.photo_attachment_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    att = await s.scalar(select(Attachment).where(Attachment.id == profile.photo_attachment_id))
    if not att or att.state != "clean":
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    settings = get_settings()
    r2_key = att.r2_key
    mime = att.mime or "application/octet-stream"

    async def _iter():
        sess = aioboto3.Session()
        async with sess.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            region_name=settings.r2_region,
            aws_access_key_id=settings.r2_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        ) as c:
            obj = await c.get_object(Bucket=settings.r2_hot_bucket, Key=r2_key)
            body = obj["Body"]
            try:
                async for chunk in body.iter_chunks(64 * 1024):
                    yield chunk
            finally:
                body.close()

    return StreamingResponse(
        _iter(),
        media_type=mime,
        headers={
            "Content-Length": str(att.bytes),
            "Cache-Control": "public, max-age=600",
        },
    )


# -- Profile sections (custom CV-style blocks) ------------------------------


class SectionIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body_md: str | None = Field(default=None, max_length=20000)
    position: int = 0


class SectionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    body_md: str | None = Field(default=None, max_length=20000)
    position: int | None = None


class SectionOut(BaseModel):
    id: str
    title: str
    body_md: str | None
    position: int


@router.get("/me/profile/sections", response_model=list[SectionOut])
async def list_my_sections(
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> list[SectionOut]:
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    rows = (
        await s.scalars(
            select(ProfileSection)
            .where(ProfileSection.profile_user_id == actor.user_id)
            .order_by(ProfileSection.position, ProfileSection.title)
        )
    ).all()
    return [SectionOut(id=r.id, title=r.title, body_md=r.body_md, position=r.position) for r in rows]


@router.post("/me/profile/sections", response_model=SectionOut)
async def create_section(
    body: SectionIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> SectionOut:
    require_csrf(request)
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    await _get_or_create_profile(s, actor.user_id)  # type: ignore[arg-type]
    sec = ProfileSection(
        profile_user_id=actor.user_id,  # type: ignore[arg-type]
        title=body.title,
        body_md=body.body_md,
        position=body.position,
    )
    s.add(sec)
    await s.flush()
    return SectionOut(id=sec.id, title=sec.title, body_md=sec.body_md, position=sec.position)


@router.patch("/me/profile/sections/{section_id}", response_model=SectionOut)
async def update_section(
    section_id: str,
    body: SectionPatch,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> SectionOut:
    require_csrf(request)
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sec = await s.scalar(select(ProfileSection).where(ProfileSection.id == section_id))
    if not sec or sec.profile_user_id != actor.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if body.title is not None:
        sec.title = body.title
    if body.body_md is not None:
        sec.body_md = body.body_md
    if body.position is not None:
        sec.position = body.position
    return SectionOut(id=sec.id, title=sec.title, body_md=sec.body_md, position=sec.position)


@router.delete("/me/profile/sections/{section_id}")
async def delete_section(
    section_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    sec = await s.scalar(select(ProfileSection).where(ProfileSection.id == section_id))
    if not sec or sec.profile_user_id != actor.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await s.delete(sec)
    return {"ok": "deleted"}


@router.get("/c/{slug}/sections", response_model=list[SectionOut])
async def list_public_sections(
    slug: str,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> list[SectionOut]:
    profile = await s.scalar(select(ContributorProfile).where(ContributorProfile.slug == slug))
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    rows = (
        await s.scalars(
            select(ProfileSection)
            .where(ProfileSection.profile_user_id == profile.user_id)
            .order_by(ProfileSection.position, ProfileSection.title)
        )
    ).all()
    return [SectionOut(id=r.id, title=r.title, body_md=r.body_md, position=r.position) for r in rows]


class ContributorCardOut(BaseModel):
    user_id: str
    slug: str
    affiliation: str | None
    bio_md: str | None
    display_name: str | None
    photo_url: str | None = None


@router.get("/contributors", response_model=list[ContributorCardOut])
async def list_contributors(
    s: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = None,
    limit: int = 60,
    offset: int = 0,
) -> list[ContributorCardOut]:
    """Public directory of contributors. Only active users with the
    `contributor` or `admin` role and a published profile slug appear."""
    from sqlalchemy import or_ as _or_

    limit = max(1, min(200, limit))
    offset = max(0, offset)
    conds = [
        User.state == "active",
        User.role.in_(("contributor", "admin")),
    ]
    if q:
        like = f"%{q}%"
        conds.append(
            _or_(
                ContributorProfile.slug.ilike(like),
                ContributorProfile.affiliation.ilike(like),
                ContributorProfile.bio_md.ilike(like),
                User.display_name.ilike(like),
            )
        )
    stmt = (
        select(ContributorProfile, User.display_name)
        .join(User, User.id == ContributorProfile.user_id)
        .where(*conds)
        .order_by(ContributorProfile.slug)
        .limit(limit)
        .offset(offset)
    )
    rows = (await s.execute(stmt)).all()
    return [
        ContributorCardOut(
            user_id=p.user_id,
            slug=p.slug,
            affiliation=p.affiliation,
            bio_md=p.bio_md,
            display_name=dn,
            photo_url=_photo_url_for(p),
        )
        for p, dn in rows
    ]


# -- Collections -------------------------------------------------------------

class CollectionIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description_md: str | None = Field(default=None, max_length=8000)
    is_course: bool = False


class CollectionOut(BaseModel):
    id: str
    owner_user_id: str
    owner_slug: str | None = None
    slug: str
    title: str
    description_md: str | None
    is_course: bool


@router.post("/collections", response_model=CollectionOut)
async def create_collection(
    body: CollectionIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> CollectionOut:
    require_csrf(request)
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    slug = normalize_slug(body.title) or "collection"
    n = 0
    base = slug
    while await s.scalar(
        select(Collection).where(Collection.owner_user_id == actor.user_id, Collection.slug == slug)
    ):
        n += 1
        slug = f"{base}-{n}"
    coll = Collection(
        owner_user_id=actor.user_id,  # type: ignore[arg-type]
        slug=slug,
        title=body.title,
        description_md=body.description_md,
        is_course=body.is_course,
    )
    s.add(coll)
    await s.flush()
    return CollectionOut(
        id=coll.id,
        owner_user_id=coll.owner_user_id,
        slug=coll.slug,
        title=coll.title,
        description_md=coll.description_md,
        is_course=coll.is_course,
    )


class CollectionItemIn(BaseModel):
    item_id: str
    position: int = Field(ge=0, default=0)
    is_required_for_course: bool = True


@router.post("/collections/{collection_id}/items")
async def add_collection_item(
    collection_id: str,
    body: CollectionItemIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    coll = await s.scalar(select(Collection).where(Collection.id == collection_id))
    if not coll:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if coll.owner_user_id != actor.user_id and actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    # Audit fix: a Contributor can only put their OWN items into their collections.
    # Admin can put any. Without this check, a Contributor could attach any other
    # author's items to their collection (IDOR / attribution misuse).
    from app.content.models import Item

    item = await s.scalar(select(Item).where(Item.id == body.item_id))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="item_not_found")
    if actor.role != "admin" and item.author_id != actor.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not_item_owner")
    s.add(
        CollectionItem(
            collection_id=collection_id,
            item_id=body.item_id,
            position=body.position,
            is_required_for_course=body.is_required_for_course,
        )
    )
    return {"ok": "true"}


# -- Collection read / update / delete --------------------------------------


@router.get("/me/collections", response_model=list[CollectionOut])
async def list_my_collections(
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> list[CollectionOut]:
    rows = (
        await s.scalars(
            select(Collection)
            .where(Collection.owner_user_id == actor.user_id)
            .order_by(Collection.created_at.desc())
        )
    ).all()
    return [
        CollectionOut(
            id=c.id,
            owner_user_id=c.owner_user_id,
            slug=c.slug,
            title=c.title,
            description_md=c.description_md,
            is_course=c.is_course,
        )
        for c in rows
    ]


async def _owner_slug_map(s: AsyncSession, owner_ids: list[str]) -> dict[str, str]:
    if not owner_ids:
        return {}
    rows = (
        await s.execute(
            select(ContributorProfile.user_id, ContributorProfile.slug).where(
                ContributorProfile.user_id.in_(set(owner_ids))
            )
        )
    ).all()
    return dict(rows)


@router.get("/collections", response_model=list[CollectionOut])
async def list_collections_public(
    s: Annotated[AsyncSession, Depends(get_session)],
    contributor: str | None = None,
    q: str | None = None,
    course_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[CollectionOut]:
    """Public browse of lecture series. Filters: contributor, free-text title/desc, course_only."""
    from sqlalchemy import or_ as _or_

    limit = max(1, min(100, limit))
    offset = max(0, offset)
    conds = []
    if contributor:
        conds.append(Collection.owner_user_id == contributor)
    if course_only:
        conds.append(Collection.is_course.is_(True))
    if q:
        like = f"%{q}%"
        conds.append(_or_(Collection.title.ilike(like), Collection.description_md.ilike(like)))
    stmt = (
        select(Collection)
        .where(*conds)
        .order_by(Collection.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await s.scalars(stmt)).all()
    slugs = await _owner_slug_map(s, [c.owner_user_id for c in rows])
    return [
        CollectionOut(
            id=c.id,
            owner_user_id=c.owner_user_id,
            owner_slug=slugs.get(c.owner_user_id),
            slug=c.slug,
            title=c.title,
            description_md=c.description_md,
            is_course=c.is_course,
        )
        for c in rows
    ]


@router.get("/items/{item_id}/collections", response_model=list[CollectionOut])
async def list_item_collections(
    item_id: str,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> list[CollectionOut]:
    """Public: which lecture series contain this item (for breadcrumb on item page)."""
    stmt = (
        select(Collection)
        .join(CollectionItem, CollectionItem.collection_id == Collection.id)
        .where(CollectionItem.item_id == item_id)
        .order_by(Collection.title)
    )
    rows = (await s.scalars(stmt)).all()
    slugs = await _owner_slug_map(s, [c.owner_user_id for c in rows])
    return [
        CollectionOut(
            id=c.id,
            owner_user_id=c.owner_user_id,
            owner_slug=slugs.get(c.owner_user_id),
            slug=c.slug,
            title=c.title,
            description_md=c.description_md,
            is_course=c.is_course,
        )
        for c in rows
    ]


class CollectionDetailOut(BaseModel):
    id: str
    owner_user_id: str
    owner_slug: str | None = None
    slug: str
    title: str
    description_md: str | None
    is_course: bool
    items: list[dict[str, Any]]


@router.get("/collections/{collection_id}", response_model=CollectionDetailOut)
async def get_collection(
    collection_id: str,
    actor: Annotated[Actor, Depends(current_actor)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> CollectionDetailOut:
    from app.content.models import Item
    from app.curation.models import CourseCompletionCriterion

    coll = await s.scalar(select(Collection).where(Collection.id == collection_id))
    if not coll:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # Public: anyone can read a collection (its listed items will be visibility-filtered).
    rows = (
        await s.execute(
            select(CollectionItem, Item)
            .join(Item, Item.id == CollectionItem.item_id)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.position)
        )
    ).all()
    rules: dict[str, Any] = {}
    if coll.is_course:
        crit = (await s.scalars(
            select(CourseCompletionCriterion).where(
                CourseCompletionCriterion.collection_id == collection_id
            )
        )).all()
        rules = {c.item_id: c.rule for c in crit}
    items: list[dict[str, Any]] = []
    for ci, it in rows:
        if it.state == "tombstoned":
            continue
        if it.state != "published" and not (
            actor.user_id == it.author_id or actor.role == "admin"
        ):
            continue
        items.append(
            {
                "id": it.id,
                "title": it.title,
                "type": it.type,
                "state": it.state,
                "position": ci.position,
                "is_required_for_course": ci.is_required_for_course,
                "completion_rule": rules.get(it.id),
            }
        )
    owner_profile = await s.scalar(
        select(ContributorProfile).where(ContributorProfile.user_id == coll.owner_user_id)
    )
    return CollectionDetailOut(
        id=coll.id,
        owner_user_id=coll.owner_user_id,
        owner_slug=owner_profile.slug if owner_profile else None,
        slug=coll.slug,
        title=coll.title,
        description_md=coll.description_md,
        is_course=coll.is_course,
        items=items,
    )


class CollectionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description_md: str | None = Field(default=None, max_length=8000)
    is_course: bool | None = None


@router.patch("/collections/{collection_id}", response_model=CollectionOut)
async def update_collection(
    collection_id: str,
    body: CollectionPatch,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> CollectionOut:
    require_csrf(request)
    coll = await s.scalar(select(Collection).where(Collection.id == collection_id))
    if not coll:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if coll.owner_user_id != actor.user_id and actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if body.title is not None:
        coll.title = body.title
    if body.description_md is not None:
        coll.description_md = body.description_md
    if body.is_course is not None:
        coll.is_course = body.is_course
    return CollectionOut(
        id=coll.id,
        owner_user_id=coll.owner_user_id,
        slug=coll.slug,
        title=coll.title,
        description_md=coll.description_md,
        is_course=coll.is_course,
    )


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    require_csrf(request)
    coll = await s.scalar(select(Collection).where(Collection.id == collection_id))
    if not coll:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if coll.owner_user_id != actor.user_id and actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    await s.delete(coll)
    return {"ok": True}


@router.delete("/collections/{collection_id}/items/{item_id}")
async def remove_collection_item(
    collection_id: str,
    item_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    require_csrf(request)
    coll = await s.scalar(select(Collection).where(Collection.id == collection_id))
    if not coll:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if coll.owner_user_id != actor.user_id and actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    ci = await s.scalar(
        select(CollectionItem).where(
            CollectionItem.collection_id == collection_id,
            CollectionItem.item_id == item_id,
        )
    )
    if ci:
        await s.delete(ci)
    return {"ok": True}


class CompletionRuleIn(BaseModel):
    rule: dict[str, Any] = Field(
        description="JSON shape: {'video_pct': 0..1} | {'article_scroll_pct': 0..1} | {'file_downloaded': true}"
    )


@router.put("/collections/{collection_id}/items/{item_id}/rule")
async def set_completion_rule(
    collection_id: str,
    item_id: str,
    body: CompletionRuleIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """FR-COL-002: per-item completion criterion in a course."""
    from app.curation.models import CourseCompletionCriterion

    require_csrf(request)
    coll = await s.scalar(select(Collection).where(Collection.id == collection_id))
    if not coll:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if coll.owner_user_id != actor.user_id and actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if not coll.is_course:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="not_a_course")
    crit = await s.scalar(
        select(CourseCompletionCriterion).where(
            CourseCompletionCriterion.collection_id == collection_id,
            CourseCompletionCriterion.item_id == item_id,
        )
    )
    if crit is None:
        crit = CourseCompletionCriterion(
            collection_id=collection_id, item_id=item_id, rule=body.rule
        )
        s.add(crit)
    else:
        crit.rule = body.rule
    return {"ok": True, "rule": body.rule}


# -- Workshops ---------------------------------------------------------------

class WorkshopIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    abstract_md: str | None = Field(default=None, max_length=8000)
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    is_online: bool = False
    registration_url: HttpUrl | None = None
    speakers: list[str] = Field(min_length=1)  # user_ids


class WorkshopOut(BaseModel):
    id: str
    title: str
    slug: str
    starts_at: datetime
    ends_at: datetime
    state: str
    is_online: bool
    location: str | None
    registration_url: str | None
    speakers: list[str]


@router.post("/workshops", response_model=WorkshopOut)
async def create_workshop(
    body: WorkshopIn,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> WorkshopOut:
    require_csrf(request)
    if actor.role not in ("contributor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if body.ends_at <= body.starts_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="ends_before_starts")
    slug = normalize_slug(body.title) or "workshop"
    n = 0
    base = slug
    while await s.scalar(select(Workshop).where(Workshop.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    w = Workshop(
        title=body.title,
        slug=slug,
        abstract_md=body.abstract_md,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        location=body.location,
        is_online=body.is_online,
        registration_url=str(body.registration_url) if body.registration_url else None,
        state="pending_review" if actor.role == "contributor" else "published",
    )
    s.add(w)
    await s.flush()
    for i, sid in enumerate(body.speakers):
        s.add(WorkshopSpeaker(workshop_id=w.id, contributor_user_id=sid, position=i))
    return WorkshopOut(
        id=w.id, title=w.title, slug=w.slug, starts_at=w.starts_at, ends_at=w.ends_at,
        state=w.state, is_online=w.is_online, location=w.location, registration_url=w.registration_url,
        speakers=body.speakers,
    )


@router.get("/workshops", response_model=list[WorkshopOut])
async def list_workshops(
    s: Annotated[AsyncSession, Depends(get_session)],
    upcoming_only: bool = False,
) -> list[WorkshopOut]:
    q = select(Workshop).where(Workshop.state == "published")
    if upcoming_only:
        q = q.where(Workshop.starts_at >= datetime.now(UTC))
    q = q.order_by(Workshop.starts_at)
    rows = (await s.scalars(q)).all()
    out: list[WorkshopOut] = []
    for w in rows:
        speakers = (await s.scalars(
            select(WorkshopSpeaker.contributor_user_id).where(WorkshopSpeaker.workshop_id == w.id).order_by(WorkshopSpeaker.position)
        )).all()
        out.append(WorkshopOut(
            id=w.id, title=w.title, slug=w.slug, starts_at=w.starts_at, ends_at=w.ends_at,
            state=w.state, is_online=w.is_online, location=w.location,
            registration_url=w.registration_url, speakers=list(speakers),
        ))
    return out


@router.get("/me/workshops", response_model=list[WorkshopOut])
async def list_my_workshops(
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> list[WorkshopOut]:
    """Workshops where the actor is listed as a speaker (any state)."""
    if not actor.user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    stmt = (
        select(Workshop)
        .join(WorkshopSpeaker, WorkshopSpeaker.workshop_id == Workshop.id)
        .where(
            WorkshopSpeaker.contributor_user_id == actor.user_id,
            Workshop.state != "tombstoned",
        )
        .order_by(Workshop.starts_at.desc())
    )
    rows = (await s.scalars(stmt)).all()
    out: list[WorkshopOut] = []
    for w in rows:
        speakers = (await s.scalars(
            select(WorkshopSpeaker.contributor_user_id).where(WorkshopSpeaker.workshop_id == w.id).order_by(WorkshopSpeaker.position)
        )).all()
        out.append(WorkshopOut(
            id=w.id, title=w.title, slug=w.slug, starts_at=w.starts_at, ends_at=w.ends_at,
            state=w.state, is_online=w.is_online, location=w.location,
            registration_url=w.registration_url, speakers=list(speakers),
        ))
    return out


# Admin workshop moderation -------------------------------------------------


@router.get("/admin/workshops", response_model=list[WorkshopOut])
async def admin_list_workshops(
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
    state: str | None = None,
) -> list[WorkshopOut]:
    if actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    q = select(Workshop)
    if state:
        q = q.where(Workshop.state == state)
    else:
        q = q.where(Workshop.state != "tombstoned")
    q = q.order_by(Workshop.starts_at.desc())
    rows = (await s.scalars(q)).all()
    out: list[WorkshopOut] = []
    for w in rows:
        speakers = (await s.scalars(
            select(WorkshopSpeaker.contributor_user_id).where(WorkshopSpeaker.workshop_id == w.id).order_by(WorkshopSpeaker.position)
        )).all()
        out.append(WorkshopOut(
            id=w.id, title=w.title, slug=w.slug, starts_at=w.starts_at, ends_at=w.ends_at,
            state=w.state, is_online=w.is_online, location=w.location,
            registration_url=w.registration_url, speakers=list(speakers),
        ))
    return out


@router.post("/admin/workshops/{workshop_id}/approve", response_model=WorkshopOut)
async def admin_approve_workshop(
    workshop_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> WorkshopOut:
    require_csrf(request)
    if actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    w = await s.scalar(select(Workshop).where(Workshop.id == workshop_id))
    if not w or w.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    w.state = "published"
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="workshop.publish",
        target_type="workshop",
        target_id=w.id,
        payload={},
    )
    speakers = (await s.scalars(
        select(WorkshopSpeaker.contributor_user_id).where(WorkshopSpeaker.workshop_id == w.id).order_by(WorkshopSpeaker.position)
    )).all()
    return WorkshopOut(
        id=w.id, title=w.title, slug=w.slug, starts_at=w.starts_at, ends_at=w.ends_at,
        state=w.state, is_online=w.is_online, location=w.location,
        registration_url=w.registration_url, speakers=list(speakers),
    )


@router.post("/admin/workshops/{workshop_id}/unpublish", response_model=WorkshopOut)
async def admin_unpublish_workshop(
    workshop_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> WorkshopOut:
    require_csrf(request)
    if actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    w = await s.scalar(select(Workshop).where(Workshop.id == workshop_id))
    if not w or w.state == "tombstoned":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    w.state = "draft"
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="workshop.unpublish",
        target_type="workshop",
        target_id=w.id,
        payload={},
    )
    speakers = (await s.scalars(
        select(WorkshopSpeaker.contributor_user_id).where(WorkshopSpeaker.workshop_id == w.id).order_by(WorkshopSpeaker.position)
    )).all()
    return WorkshopOut(
        id=w.id, title=w.title, slug=w.slug, starts_at=w.starts_at, ends_at=w.ends_at,
        state=w.state, is_online=w.is_online, location=w.location,
        registration_url=w.registration_url, speakers=list(speakers),
    )


@router.delete("/admin/workshops/{workshop_id}")
async def admin_delete_workshop(
    workshop_id: str,
    request: Request,
    actor: Annotated[Actor, Depends(require_user)],
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    require_csrf(request)
    if actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    w = await s.scalar(select(Workshop).where(Workshop.id == workshop_id))
    if not w:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    w.state = "tombstoned"
    await audit_record(
        s,
        actor_user_id=actor.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="workshop.delete",
        target_type="workshop",
        target_id=w.id,
        payload={},
    )
    return {"id": w.id, "state": w.state}
