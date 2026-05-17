"""Argon2id password hashing with server-side pepper."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.core.settings import get_settings

# m=64 MiB, t=3, p=1 — meets NFR-SEC-001
_PH = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def _peppered(password: str) -> str:
    pepper = get_settings().auth_password_pepper.get_secret_value()
    return pepper + password


def hash_password(password: str) -> str:
    return _PH.hash(_peppered(password))


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        _PH.verify(stored_hash, _peppered(password))
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _PH.check_needs_rehash(stored_hash)


# Dummy hash used to defeat user-enumeration via timing on forgot-pwd / login
# (D-19). The string is deterministic and known-invalid for any password.
DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=1$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def dummy_verify(password: str) -> None:
    """Constant-ish-time verify against a dummy hash. Always returns None.

    Use on the negative branch of login / forgot-password to keep timing balanced.
    """
    try:
        _PH.verify(DUMMY_HASH, _peppered(password))
    except Exception:
        pass
