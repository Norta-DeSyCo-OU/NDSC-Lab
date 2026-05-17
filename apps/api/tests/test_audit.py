from __future__ import annotations

# Env bootstrap.
from tests.test_argon2 import _pem  # noqa: F401

from app.core.audit import _canon, _prune_pii


def test_prune_pii() -> None:
    p = {"ip": "1.2.3.4", "ua": "x", "email": "a@b", "kept": True}
    pruned = _prune_pii(p)
    assert "ip" not in pruned
    assert "ua" not in pruned
    assert "email" not in pruned
    assert pruned["kept"] is True


def test_canon_deterministic() -> None:
    a = _canon(action="x", target_type="y", target_id="1", ts_epoch=1000.0, payload_pruned={"b": 1, "a": 2})
    b = _canon(action="x", target_type="y", target_id="1", ts_epoch=1000.0, payload_pruned={"a": 2, "b": 1})
    assert a == b  # sort_keys ensures determinism
