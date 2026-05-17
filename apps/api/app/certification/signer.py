"""Ed25519 cert signer.

Implements the NDSC-cert v1 envelope: detached Ed25519 signature over the
unsigned PDF bytes; signature + key_id embedded in the PDF metadata.

Pluggable artifact producer interface — `Signer` produces (PDF, signature).
A future VC artifact producer can implement the same interface (FR-CERT-006).
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.core.settings import get_settings


@dataclass(frozen=True, slots=True)
class SignResult:
    signature_b64: str
    key_id: str


def _load_priv() -> Ed25519PrivateKey:
    s = get_settings()
    pem = s.cert_ed25519_private_key_pem.get_secret_value().encode()
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise RuntimeError("cert_ed25519_private_key_pem is not an Ed25519 private key")
    return key


def public_key_pem() -> str:
    pub = _load_priv().public_key()
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def sign_bytes(data: bytes) -> SignResult:
    s = get_settings()
    sig = _load_priv().sign(data)
    return SignResult(signature_b64=base64.b64encode(sig).decode(), key_id=s.cert_ed25519_key_id)


def verify_bytes(data: bytes, signature_b64: str, public_key_pem_str: str) -> bool:
    try:
        pub = serialization.load_pem_public_key(public_key_pem_str.encode())
        if not isinstance(pub, Ed25519PublicKey):
            return False
        pub.verify(base64.b64decode(signature_b64), data)
        return True
    except Exception:
        return False
