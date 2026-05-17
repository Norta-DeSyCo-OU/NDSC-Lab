"""Centralized typed settings — env-only secrets, no defaults that ship secret data."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    database_url: SecretStr
    redis_url: SecretStr

    r2_endpoint_url: str
    r2_region: str = "auto"
    r2_access_key_id: SecretStr
    r2_secret_access_key: SecretStr
    r2_hot_bucket: str
    r2_cold_bucket: str

    auth_password_pepper: SecretStr
    audit_hmac_key: SecretStr
    session_signing_key: SecretStr
    cert_ed25519_private_key_pem: SecretStr
    cert_ed25519_key_id: str = "k1"

    google_oauth_client_id: SecretStr | None = None
    google_oauth_client_secret: SecretStr | None = None

    resend_api_key: SecretStr | None = None
    resend_from_email: str = "noreply@example.invalid"

    sentry_dsn: str | None = None

    clamav_host: str = "clamav"
    clamav_port: int = 3310

    rate_limit_login_per_ip_15m: int = 5
    rate_limit_login_per_account_15m: int = 10
    rate_limit_password_reset_per_account_h: int = 5
    rate_limit_comment_per_user_min: int = 5
    rate_limit_view_event_per_user_min: int = 30
    rate_limit_generic_per_ip_min: int = 100

    cookie_secure: bool = True
    cookie_domain: str | None = None
    session_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days
    csrf_cookie_name: str = "ndsc_csrf"
    session_cookie_name: str = "ndsc_sess"

    min_age_years: int = 16

    cdn_purge_token: SecretStr | None = None

    @field_validator("cert_ed25519_private_key_pem", mode="before")
    @classmethod
    def _unescape_pem(cls, v):  # type: ignore[no-untyped-def]
        """Allow PEM to be passed via env as a single line with literal `\\n`.

        Docker Compose env_file does not support multi-line values, so the PEM is
        often stored with `\n` escaped. Convert it back to real newlines here.
        """
        if v is None:
            return v
        s = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if "\\n" in s and "\n" not in s:
            s = s.replace("\\n", "\n")
        return s


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
