from __future__ import annotations

from dataclasses import dataclass

import pytest

from community_energy_flex.auth import (
    AccessDenied,
    CsvAuditLog,
    Permission,
    Role,
    User,
    authorize,
    can,
    permissions_for,
    require,
    scope_rows,
    visible_pages,
)


@dataclass(frozen=True)
class Row:
    household_id: str
    community_id: str


ROWS = [
    Row("C1-H1", "C1"),
    Row("C1-H2", "C1"),
    Row("C2-H1", "C2"),
]


# --- roles / permissions ----------------------------------------------------

def test_admin_has_every_permission():
    assert permissions_for(Role.ADMIN) == frozenset(Permission)


def test_household_cannot_manage_users_or_see_community():
    assert can(Role.HOUSEHOLD, Permission.RUN_OPTIMISER)
    assert not can(Role.HOUSEHOLD, Permission.MANAGE_USERS)
    assert not can(Role.HOUSEHOLD, Permission.VIEW_COMMUNITY_REPORTS)


def test_community_manager_sees_community_not_optimiser():
    assert can(Role.COMMUNITY_MANAGER, Permission.VIEW_COMMUNITY_REPORTS)
    assert not can(Role.COMMUNITY_MANAGER, Permission.RUN_OPTIMISER)


def test_visible_pages_are_role_gated():
    assert "Admin" not in visible_pages(Role.HOUSEHOLD)
    assert "Admin" in visible_pages(Role.ADMIN)
    assert "Home" in visible_pages(Role.PUBLIC)  # always visible
    assert "Add Tasks" not in visible_pages(Role.PUBLIC)


# --- row-level scoping ------------------------------------------------------

def test_household_sees_only_their_own_rows():
    user = User("C1-H1", Role.HOUSEHOLD, community_id="C1")
    assert scope_rows(user, ROWS) == [Row("C1-H1", "C1")]


def test_community_manager_sees_only_their_community():
    user = User("mgr", Role.COMMUNITY_MANAGER, community_id="C1")
    scoped = scope_rows(user, ROWS)
    assert {r.household_id for r in scoped} == {"C1-H1", "C1-H2"}


def test_analyst_and_admin_see_everything():
    assert scope_rows(User("a", Role.ANALYST), ROWS) == ROWS
    assert scope_rows(User("b", Role.ADMIN), ROWS) == ROWS


def test_public_sees_no_real_rows():
    assert scope_rows(User("guest", Role.PUBLIC), ROWS) == []


def test_require_raises_for_missing_permission():
    with pytest.raises(AccessDenied):
        require(User("C1-H1", Role.HOUSEHOLD), Permission.MANAGE_USERS)
    require(User("C1-H1", Role.HOUSEHOLD), Permission.RUN_OPTIMISER)  # no raise


# --- authorize + audit ------------------------------------------------------

def test_authorize_logs_allowed_and_denied(tmp_path):
    audit = CsvAuditLog(tmp_path)
    admin = User("root", Role.ADMIN)
    household = User("C1-H1", Role.HOUSEHOLD)

    authorize(admin, Permission.MANAGE_USERS, "users", audit=audit)
    with pytest.raises(AccessDenied):
        authorize(household, Permission.MANAGE_USERS, "users", audit=audit)

    rows = audit.read()
    assert len(rows) == 2
    assert rows[0]["allowed"] == "True" and rows[0]["role"] == "admin"
    assert rows[1]["allowed"] == "False" and rows[1]["role"] == "household"
    assert rows[1]["action"] == "manage_users"
    assert all(r["at"] for r in rows)  # timestamps stamped
