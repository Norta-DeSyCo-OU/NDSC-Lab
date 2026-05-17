"""Markdown rendering + sanitization."""
from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark").enable("table").enable("strikethrough")

_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "em", "u", "s", "del", "ins",
    "blockquote", "code", "pre", "kbd", "samp", "mark",
    "ul", "ol", "li",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "sup", "sub",
    "div", "span",
}

_ALLOWED_ATTRS = {
    "a": {"href", "title", "target"},  # rel is managed by nh3 via link_rel
    "img": {"src", "alt", "title", "width", "height"},
    "code": {"class"},
    "pre": {"class"},
    "th": {"align"},
    "td": {"align"},
    "div": {"class"},
    "span": {"class"},
}

_URL_SCHEMES = {"http", "https", "mailto"}


def render(md_text: str) -> str:
    raw = _md.render(md_text or "")
    cleaned = nh3.clean(
        raw,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes=_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )
    return cleaned
