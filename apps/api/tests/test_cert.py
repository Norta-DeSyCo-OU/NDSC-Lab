from __future__ import annotations

from datetime import datetime, timezone

# env bootstrap via shared fixture
from tests.test_argon2 import _pem  # noqa: F401  side-effect: ensures env set

from app.certification.pdf import extract_signature, render_and_sign, strip_signature
from app.certification.signer import public_key_pem, verify_bytes


def test_sign_and_verify_roundtrip() -> None:
    r = render_and_sign(
        cert_id="01J000000000000000000TEST1",
        recipient="Dr. Ada Lovelace",
        course="ZKP Fundamentals — Part 1",
        issued_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
    )
    cert_id, key_id, sig = extract_signature(r.pdf_bytes)
    assert cert_id == "01J000000000000000000TEST1"
    assert key_id == "k1"
    assert sig and len(sig) > 40

    canonical = strip_signature(r.pdf_bytes)
    assert verify_bytes(canonical, sig, public_key_pem()) is True


def test_tamper_detection() -> None:
    r = render_and_sign(
        cert_id="01J000000000000000000TEST2",
        recipient="Tamper Target",
        course="X",
        issued_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
    )
    canonical = strip_signature(r.pdf_bytes)
    # Flip a byte somewhere in the middle of the canonical body. PDF text may be
    # compressed/encoded, so manipulating a known string is unreliable across
    # builds; a single-byte flip in any data stream is enough to break Ed25519.
    tampered = bytearray(canonical)
    flip_at = len(tampered) // 2
    tampered[flip_at] ^= 0xFF
    _, _, sig = extract_signature(r.pdf_bytes)
    assert sig
    assert verify_bytes(bytes(tampered), sig, public_key_pem()) is False
