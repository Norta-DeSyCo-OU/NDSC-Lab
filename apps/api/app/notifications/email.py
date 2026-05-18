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


async def send_admin_alert_email(to: str, *, event: str, count: int, threshold: int, window_s: int) -> None:
    """Sent to every admin when an activity threshold is exceeded."""
    s = get_settings()
    link = f"{s.frontend_base_url}/admin/security"
    pretty = {
        "signup": "signups",
        "failed_login": "failed login attempts",
        "item_publish": "item publishes",
    }.get(event, event)
    await _send(
        to=to,
        subject=f"NDSC Lab — activity alert: {pretty}",
        html=(
            f"<p><strong>{count}</strong> {pretty} in the last "
            f"{window_s // 60} minutes (threshold: {threshold}).</p>"
            f'<p>Inspect at <a href="{link}">{link}</a>. The cooldown auto-resets after the '
            f"configured period; click <em>Release cooldown</em> to reset early.</p>"
        ),
    )


async def send_admin_digest_email(to: str, *, period_days: int, summary: dict) -> None:
    """Periodic digest of platform activity."""
    s = get_settings()
    link = f"{s.frontend_base_url}/admin"
    rows = "".join(
        f"<tr><td>{k}</td><td style='text-align:right'><strong>{v}</strong></td></tr>"
        for k, v in summary.items()
    )
    await _send(
        to=to,
        subject=f"NDSC Lab — {period_days}-day admin digest",
        html=(
            f"<h2>Activity summary — last {period_days} days</h2>"
            f"<table cellpadding='4' style='border-collapse:collapse'>{rows}</table>"
            f'<p>Full dashboards at <a href="{link}">{link}</a>.</p>'
        ),
    )
