from __future__ import annotations

from app.content.slug import is_reserved, normalize_slug

# Env bootstrap.
from tests.test_argon2 import _pem  # noqa: F401


def test_normalize_basic() -> None:
    assert normalize_slug("Hello World") == "hello-world"


def test_normalize_unicode() -> None:
    assert normalize_slug("Café & Résumé") == "cafe-resume"


def test_normalize_collapses_dashes() -> None:
    assert normalize_slug("foo----bar") == "foo-bar"


def test_normalize_strips_leading_trailing() -> None:
    assert normalize_slug("---foo---") == "foo"


def test_reserved_blocked() -> None:
    assert is_reserved("admin") is True
    assert is_reserved("api") is True
    assert is_reserved("c") is True
    assert is_reserved("foo-bar") is False
