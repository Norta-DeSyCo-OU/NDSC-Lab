from __future__ import annotations

# Env bootstrap.
from tests.test_argon2 import _pem  # noqa: F401

from app.content.markdown import render


def test_basic_markdown_renders() -> None:
    h = render("# Title\n\nHello **world**.")
    assert "<h1>Title</h1>" in h
    assert "<strong>world</strong>" in h


def test_strips_script_tag() -> None:
    h = render('Hello <script>alert(1)</script> world')
    assert "<script" not in h
    assert "alert" not in h or "&lt;script" in h


def test_strips_javascript_url() -> None:
    h = render('[click me](javascript:alert(1))')
    # The dangerous scheme must not survive as an anchor href. Plain-text
    # appearance of the scheme is acceptable; what matters is no <a href="javascript:...">.
    assert 'href="javascript:' not in h
    assert "<a" not in h or 'href="javascript:' not in h


def test_allows_https_link_with_rel_nofollow() -> None:
    h = render("[example](https://example.com)")
    assert 'href="https://example.com"' in h
    assert "nofollow" in h


def test_strips_iframe() -> None:
    h = render('<iframe src="https://evil"></iframe>Hi')
    assert "<iframe" not in h
    assert "Hi" in h


def test_strips_event_handler() -> None:
    h = render('<a href="https://example.com" onclick="alert(1)">x</a>')
    assert "onclick" not in h
    assert "alert" not in h or "&quot;alert" in h
