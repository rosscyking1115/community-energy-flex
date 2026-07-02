"""Row-level data scoping - the enforcement that a household never sees another
household's data, and a community manager sees only their community.

Kept generic: any record exposing ``household_id`` and ``community_id`` can be
scoped, so the same rule applies to schedules, savings rows, and reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from community_energy_flex.auth.roles import Permission, Role, can


class AccessDenied(PermissionError):
    """Raised when a user lacks a required permission."""


@dataclass(frozen=True)
class User:
    user_id: str
    role: Role
    community_id: str | None = None


@runtime_checkable
class OwnedRecord(Protocol):
    household_id: str
    community_id: str


T = TypeVar("T", bound=OwnedRecord)


def scope_rows(user: User, rows: list[T]) -> list[T]:
    """Return only the rows ``user`` is allowed to see.

    * household -> only rows for their own ``household_id``
    * community manager -> only rows in their ``community_id``
    * analyst / admin -> all rows
    * public -> none (demo mode serves sample data separately, never real rows)
    """
    if user.role in (Role.ANALYST, Role.ADMIN):
        return list(rows)
    if user.role is Role.HOUSEHOLD:
        return [r for r in rows if r.household_id == user.user_id]
    if user.role is Role.COMMUNITY_MANAGER:
        return [r for r in rows if r.community_id == user.community_id]
    return []  # PUBLIC and anything else: no real data


def require(user: User, permission: Permission) -> None:
    """Raise :class:`AccessDenied` if ``user`` lacks ``permission``."""
    if not can(user.role, permission):
        raise AccessDenied(
            f"user '{user.user_id}' (role {user.role}) lacks permission '{permission}'"
        )
