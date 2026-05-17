from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.policy import Actor, PolicyError, authorize

ANON = Actor(user_id=None, role=None)
USER = Actor(user_id="u1", role="user")
CONTRIB_A = Actor(user_id="c1", role="contributor")
CONTRIB_B = Actor(user_id="c2", role="contributor")
ADMIN = Actor(user_id="a1", role="admin")


@dataclass
class Item:
    author_id: str
    state: str = "draft"


def test_anon_can_read_published() -> None:
    authorize(ANON, "item.read.published")


def test_anon_cannot_create_item() -> None:
    with pytest.raises(PolicyError):
        authorize(ANON, "item.create")


def test_user_cannot_create_item() -> None:
    with pytest.raises(PolicyError):
        authorize(USER, "item.create")


def test_contributor_can_create_item() -> None:
    authorize(CONTRIB_A, "item.create")


def test_contributor_cannot_publish() -> None:
    with pytest.raises(PolicyError):
        authorize(CONTRIB_A, "item.publish", Item(author_id="c1"))


def test_admin_can_publish() -> None:
    authorize(ADMIN, "item.publish", Item(author_id="c1"))


def test_contributor_cannot_edit_other_draft() -> None:
    with pytest.raises(PolicyError):
        authorize(CONTRIB_B, "item.update", Item(author_id="c1"))


def test_contributor_can_edit_own_draft() -> None:
    authorize(CONTRIB_A, "item.update", Item(author_id="c1"))


def test_contributor_can_edit_own_published() -> None:
    # FR-CONTENT-012c: authors retain edit rights on their published items.
    authorize(CONTRIB_A, "item.update", Item(author_id="c1", state="published"))


def test_contributor_cannot_edit_pending_review() -> None:
    # Pending review is locked until admin decides.
    with pytest.raises(PolicyError):
        authorize(CONTRIB_A, "item.update", Item(author_id="c1", state="pending_review"))


def test_admin_only_actions() -> None:
    for action in (
        "cert.issue",
        "cert.revoke",
        "user.role.grant",
        "user.ban",
        "platform_setting.write",
        "takedown.decide",
        "analytics.read",
    ):
        authorize(ADMIN, action)
        with pytest.raises(PolicyError):
            authorize(USER, action)
        with pytest.raises(PolicyError):
            authorize(CONTRIB_A, action)
        with pytest.raises(PolicyError):
            authorize(ANON, action)


def test_unknown_action_default_denies() -> None:
    with pytest.raises(PolicyError):
        authorize(ADMIN, "made.up.action")
