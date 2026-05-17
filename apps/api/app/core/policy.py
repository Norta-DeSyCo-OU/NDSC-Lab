"""Central authorization policy module.

Single decision point. Default-deny. Every mutating handler must call `authorize`.

Tested in `tests/test_policy.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Role = Literal["user", "contributor", "admin"]


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: str | None
    role: Role | None  # None when anonymous


class PolicyError(Exception):
    pass


def _is_admin(actor: Actor) -> bool:
    return actor.role == "admin"


def _is_contributor_or_higher(actor: Actor) -> bool:
    return actor.role in ("contributor", "admin")


def _is_authed(actor: Actor) -> bool:
    return actor.user_id is not None and actor.role is not None


def authorize(actor: Actor, action: str, resource: Any | None = None) -> None:
    """Raise PolicyError if action not allowed for actor on resource.

    Default-deny: any action not explicitly listed below raises.
    """
    if action == "item.read.published":
        return  # public

    if action == "item.read.draft":
        if _is_admin(actor):
            return
        if (
            resource is not None
            and getattr(resource, "author_id", None) == actor.user_id
        ):
            return
        raise PolicyError(action)

    if action == "item.create":
        if _is_contributor_or_higher(actor):
            return
        raise PolicyError(action)

    if action == "item.update":
        if _is_admin(actor):
            return
        # FR-CONTENT-012c: author may edit own draft OR published item. Tombstoned
        # and pending_review are locked (admin must unpublish / approve first).
        if (
            _is_contributor_or_higher(actor)
            and resource is not None
            and getattr(resource, "author_id", None) == actor.user_id
            and getattr(resource, "state", None) in ("draft", "published")
        ):
            return
        raise PolicyError(action)

    if action == "item.submit":
        if (
            _is_contributor_or_higher(actor)
            and resource is not None
            and getattr(resource, "author_id", None) == actor.user_id
            and getattr(resource, "state", None) == "draft"
        ):
            return
        raise PolicyError(action)

    if action == "item.publish":
        if _is_admin(actor):
            return
        raise PolicyError(action)

    if action == "item.delete":
        if _is_admin(actor):
            return
        if (
            _is_contributor_or_higher(actor)
            and resource is not None
            and getattr(resource, "author_id", None) == actor.user_id
        ):
            return
        raise PolicyError(action)

    if action == "comment.create":
        if _is_authed(actor):
            return
        raise PolicyError(action)

    if action == "comment.update":
        if (
            _is_authed(actor)
            and resource is not None
            and getattr(resource, "author_id", None) == actor.user_id
        ):
            return
        raise PolicyError(action)

    if action == "comment.delete":
        if _is_admin(actor):
            return
        if (
            _is_authed(actor)
            and resource is not None
            and getattr(resource, "author_id", None) == actor.user_id
        ):
            return
        raise PolicyError(action)

    if action == "analytics.read":
        if _is_admin(actor):
            return
        raise PolicyError(action)

    if action == "cert.issue" or action == "cert.revoke":
        if _is_admin(actor):
            return
        raise PolicyError(action)

    if action == "user.role.grant" or action == "user.role.revoke" or action == "user.ban":
        if _is_admin(actor):
            return
        raise PolicyError(action)

    if action == "platform_setting.write":
        if _is_admin(actor):
            return
        raise PolicyError(action)

    if action == "contributor_tunable.write":
        if _is_admin(actor):
            return
        raise PolicyError(action)

    if action == "takedown.decide":
        if _is_admin(actor):
            return
        raise PolicyError(action)

    raise PolicyError(f"unknown_action:{action}")
