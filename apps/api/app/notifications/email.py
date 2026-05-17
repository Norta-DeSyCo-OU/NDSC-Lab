"""Transactional email via Resend (log-only in dev when no API key)."""
from __future__ import annotations

import httpx

from app.core.settings import get_settings
from app.core.telemetry import log

_API = "https://api.resend.com/emails"


async def _send(*, to: str, subject: str, html: str) -> None:
    s = get_settings()
    if not s.resend_api_key:
        log.info("email_dev_log", to=to, subject=subject)
        return
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(
            _API,
            headers={
                "Authorization": f"Bearer {s.resend_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json={
                "from": s.resend_from_email,
                "to": [to],
                "subject": subject,
                "html": html,
            },
        )
        r.raise_for_status()


async def send_verification_email(to: str, token: str) -> None:
    s = get_settings()
    link = f"{s.frontend_base_url}/auth/verify?t={token}"
    await _send(
        to=to,
        subject="NDSC Lab — confirm your email",
        html=f'<p>Confirm your email by clicking <a href="{link}">this link</a> (valid 24 h).</p>',
    )


async def send_password_reset_email(to: str, token: str) -> None:
    s = get_settings()
    link = f"{s.frontend_base_url}/auth/reset?t={token}"
    await _send(
        to=to,
        subject="NDSC Lab — password reset",
        html=f'<p>Reset your password by clicking <a href="{link}">this link</a> (valid 1 h).</p>',
    )


async def send_cert_issued_email(to: str, cert_id: str) -> None:
    s = get_settings()
    link = f"{s.frontend_base_url}/me/certificates"
    await _send(
        to=to,
        subject="NDSC Lab — your certificate is ready",
        html=f'<p>Your certificate <strong>{cert_id}</strong> is available <a href="{link}">in your account</a>.</p>',
    )
