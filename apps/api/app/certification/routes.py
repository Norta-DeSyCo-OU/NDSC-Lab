"""Certificate routes: admin issuance + public verification."""
from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.certification.models import CertAdminPseudonym, Certificate, SigningKey
from app.certification.pdf import extract_signature, render_and_sign, strip_signature
from app.certification.signer import public_key_pem, verify_bytes
from app.core.audit import record as audit_record
from app.core.db import get_session
from app.core.security.csrf import require_csrf
from app.core.settings import get_settings
from app.identity.deps import require_admin
from app.identity.models import User

router = APIRouter(tags=["certification"])


class IssueIn(BaseModel):
    user_id: str
    collection_id: str
    course_title: str


class CertOut(BaseModel):
    id: str
    user_id: str
    collection_id: str
    issued_at: datetime
    signing_key_id: str
    revoked_at: datetime | None


class VerifyOut(BaseModel):
    cert_id: str
    issued_at: datetime | None
    revoked: bool
    recipient_display_name: str | None
    issuer_label: str
    valid: bool | None = None  # None when just GET; bool only when PDF posted


@router.post("/admin/certificates", response_model=CertOut)
async def issue_cert(
    body: IssueIn,
    request: Request,
    admin=Depends(require_admin),  # noqa: B008
    s: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
) -> CertOut:
    require_csrf(request)
    user = await s.scalar(select(User).where(User.id == body.user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")

    settings = get_settings()
    sk = await s.scalar(
        select(SigningKey).where(SigningKey.key_id == settings.cert_ed25519_key_id)
    )
    if not sk:
        sk = SigningKey(
            key_id=settings.cert_ed25519_key_id,
            algo="ed25519",
            public_key_pem=public_key_pem(),
            private_key_ref="env:CERT_ED25519_PRIVATE_KEY_PEM",
            state="active",
        )
        s.add(sk)
        await s.flush()

    cert = Certificate(
        user_id=user.id,
        collection_id=body.collection_id,
        issued_by_admin_id=admin.user_id,  # type: ignore[arg-type]
        signing_key_id=sk.key_id,
        signature_b64="",  # set below
    )
    s.add(cert)
    await s.flush()

    rendered = render_and_sign(
        cert_id=cert.id,
        recipient=user.display_name or user.email,
        course=body.course_title,
        issued_at=cert.issued_at or datetime.now(UTC),
    )
    cert.signature_b64 = rendered.signature_b64

    await audit_record(
        s,
        actor_user_id=admin.user_id,
        actor_ip=request.client.host if request.client else None,
        actor_ua=request.headers.get("user-agent"),
        action="cert.issue",
        target_type="certificate",
        target_id=cert.id,
        payload={"user_id": user.id, "collection_id": body.collection_id},
    )

    return CertOut(
        id=cert.id,
        user_id=cert.user_id,
        collection_id=cert.collection_id,
        issued_at=cert.issued_at,
        signing_key_id=cert.signing_key_id,
        revoked_at=cert.revoked_at,
    )


class RevokeIn(BaseModel):
    reason: str | None = None


@router.post("/admin/certificates/{cert_id}/revoke", response_model=CertOut)
async def revoke_cert(
    cert_id: str,
    body: RevokeIn,
    request: Request,
    admin=Depends(require_admin),  # noqa: B008
    s: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
) -> CertOut:
    require_csrf(request)
    cert = await s.scalar(select(Certificate).where(Certificate.id == cert_id))
    if not cert:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if cert.revoked_at is None:
        cert.revoked_at = datetime.now(UTC)
        cert.revoke_reason = body.reason
        await audit_record(
            s,
            actor_user_id=admin.user_id,
            actor_ip=request.client.host if request.client else None,
            actor_ua=request.headers.get("user-agent"),
            action="cert.revoke",
            target_type="certificate",
            target_id=cert.id,
            payload={"reason": body.reason},
        )
    return CertOut(
        id=cert.id,
        user_id=cert.user_id,
        collection_id=cert.collection_id,
        issued_at=cert.issued_at,
        signing_key_id=cert.signing_key_id,
        revoked_at=cert.revoked_at,
    )


@router.get("/verify/{cert_id}", response_model=VerifyOut)
async def verify_cert(
    cert_id: str,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> VerifyOut:
    cert = await s.scalar(select(Certificate).where(Certificate.id == cert_id))
    if not cert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="cert_not_found")
    user = await s.scalar(select(User).where(User.id == cert.user_id))

    issuer_label = "NDSC Lab"
    pseudonym = await s.scalar(
        select(CertAdminPseudonym).where(
            CertAdminPseudonym.original_admin_id == cert.issued_by_admin_id
        )
    )
    if pseudonym is not None:
        issuer_label = "NDSC Lab (admin record redacted)"

    return VerifyOut(
        cert_id=cert.id,
        issued_at=cert.issued_at,
        revoked=cert.revoked_at is not None,
        recipient_display_name=(user.display_name if user else None),
        issuer_label=issuer_label,
        valid=None,
    )


@router.post("/verify/{cert_id}", response_model=VerifyOut)
async def verify_cert_pdf(
    cert_id: str,
    pdf: UploadFile,
    s: Annotated[AsyncSession, Depends(get_session)],
) -> VerifyOut:
    cert = await s.scalar(select(Certificate).where(Certificate.id == cert_id))
    if not cert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="cert_not_found")

    # D-20: check revocation BEFORE signature verify (defends against timing enumeration).
    if cert.revoked_at is not None:
        user = await s.scalar(select(User).where(User.id == cert.user_id))
        return VerifyOut(
            cert_id=cert.id,
            issued_at=cert.issued_at,
            revoked=True,
            recipient_display_name=(user.display_name if user else None),
            issuer_label="NDSC Lab",
            valid=False,
        )

    body = await pdf.read()
    try:
        cert_id_in_pdf, key_id, sig = extract_signature(body)
    except Exception:
        # Malformed PDF → treat as invalid signature (not a server error).
        return VerifyOut(
            cert_id=cert.id,
            issued_at=cert.issued_at,
            revoked=False,
            recipient_display_name=(await s.scalar(select(User).where(User.id == cert.user_id))).display_name if cert.user_id else None,  # type: ignore[union-attr]
            issuer_label="NDSC Lab",
            valid=False,
        )
    if not (cert_id_in_pdf == cert.id and sig and key_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="signature_missing")
    try:
        canonical = strip_signature(body)
    except Exception:
        user = await s.scalar(select(User).where(User.id == cert.user_id))
        return VerifyOut(
            cert_id=cert.id,
            issued_at=cert.issued_at,
            revoked=False,
            recipient_display_name=(user.display_name if user else None),
            issuer_label="NDSC Lab",
            valid=False,
        )

    sk = await s.scalar(select(SigningKey).where(SigningKey.key_id == key_id))
    if not sk:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="unknown_signing_key")
    valid = verify_bytes(canonical, sig, sk.public_key_pem)

    user = await s.scalar(select(User).where(User.id == cert.user_id))
    return VerifyOut(
        cert_id=cert.id,
        issued_at=cert.issued_at,
        revoked=False,
        recipient_display_name=(user.display_name if user else None),
        issuer_label="NDSC Lab",
        valid=valid,
    )


@router.get("/.well-known/ndsc-cert-pubkey.json")
async def well_known_pubkey(
    s: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    keys = (await s.scalars(select(SigningKey))).all()
    return {
        "keys": [
            {"key_id": k.key_id, "algo": k.algo, "public_key_pem": k.public_key_pem, "state": k.state}
            for k in keys
        ]
    }


@router.get("/admin/certificates/{cert_id}/pdf")
async def download_cert_pdf(
    cert_id: str,
    admin=Depends(require_admin),  # noqa: B008
    s: AsyncSession = Depends(get_session),  # noqa: B008
) -> StreamingResponse:
    cert = await s.scalar(select(Certificate).where(Certificate.id == cert_id))
    if not cert:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    user = await s.scalar(select(User).where(User.id == cert.user_id))
    rendered = render_and_sign(
        cert_id=cert.id,
        recipient=(user.display_name if user and user.display_name else (user.email if user else cert.user_id)),
        course=cert.collection_id,  # title resolved fully when Collection model lands
        issued_at=cert.issued_at,
    )
    return StreamingResponse(
        io.BytesIO(rendered.pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ndsc-cert-{cert.id}.pdf"'},
    )
