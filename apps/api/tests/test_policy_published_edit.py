"""Unit-test for FR-CONTENT-012c policy widening."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.policy import Actor, PolicyError, authorize

# Env bootstrap.
from tests.test_argon2 import _pem  # noqa: F401


@dataclass
class Item:
    author_id: str
    state: str = "draft"


CONTRIB = Actor(user_id="c1", role="contributor")
OTHER = Actor(user_id="c2", role="contributor")
ADMIN = Actor(user_id="a1", role="admin")


def test_author_can_update_own_published_item():
    authorize(CONTRIB, "item.update", Item(author_id="c1", state="published"))


def test_author_cannot_update_own_pending_review_item():
    with pytest.raises(PolicyError):
        authorize(CONTRIB, "item.update", Item(author_id="c1", state="pending_review"))


def test_other_contributor_cannot_update_published():
    with pytest.raises(PolicyError):
        authorize(OTHER, "item.update", Item(author_id="c1", state="published"))


def test_admin_can_update_any_state():
    authorize(ADMIN, "item.update", Item(author_id="c1", state="published"))
    authorize(ADMIN, "item.update", Item(author_id="c1", state="pending_review"))
    authorize(ADMIN, "item.update", Item(author_id="c1", state="draft"))
