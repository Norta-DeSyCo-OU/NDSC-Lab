from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("R2_ENDPOINT_URL", "https://x")
os.environ.setdefault("R2_ACCESS_KEY_ID", "x")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "x")
os.environ.setdefault("R2_HOT_BUCKET", "x")
os.environ.setdefault("R2_COLD_BUCKET", "x")
os.environ.setdefault("AUTH_PASSWORD_PEPPER", "test-pepper")
os.environ.setdefault("AUDIT_HMAC_KEY", "test-key")
os.environ.setdefault("SESSION_SIGNING_KEY", "test-key")
# Generate ephemeral Ed25519 PEM for cert tests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

_pem = Ed25519PrivateKey.generate().private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
os.environ.setdefault("CERT_ED25519_PRIVATE_KEY_PEM", _pem)

from app.core.security.argon2 import hash_password, needs_rehash, verify_password


def test_hash_verify_roundtrip() -> None:
    h = hash_password("correct horse battery staple xx")
    assert verify_password(h, "correct horse battery staple xx") is True
    assert verify_password(h, "wrong password 12345678") is False


def test_pepper_affects_hash() -> None:
    h1 = hash_password("hello world 12345")
    h2 = hash_password("hello world 12345")
    assert h1 != h2  # different salt
    assert verify_password(h1, "hello world 12345")
    assert verify_password(h2, "hello world 12345")


def test_needs_rehash_for_legacy_hash() -> None:
    weak = "$argon2id$v=19$m=4096,t=1,p=1$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert needs_rehash(weak) is True
