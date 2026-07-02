"""Roles, permissions, and the mapping between them.

Permissions are explicit (no inheritance magic) so the matrix is auditable at a
glance. ``ADMIN`` holds every permission.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    PUBLIC = "public"  # demo data only
    HOUSEHOLD = "household"  # own tasks, own optimiser, own reports
    COMMUNITY_MANAGER = "community_manager"  # aggregated reports for own community
    ANALYST = "analyst"  # manage tariffs, inspect data quality, review runs
    ADMIN = "admin"  # everything, plus user/role and pipeline management


class Permission(StrEnum):
    VIEW_DEMO = "view_demo"
    RUN_OPTIMISER = "run_optimiser"
    VIEW_OWN_REPORTS = "view_own_reports"
    VIEW_COMMUNITY_REPORTS = "view_community_reports"
    MANAGE_TARIFFS = "manage_tariffs"
    INSPECT_DATA_QUALITY = "inspect_data_quality"
    MANAGE_USERS = "manage_users"
    MANAGE_PIPELINE = "manage_pipeline"


_ALL: frozenset[Permission] = frozenset(Permission)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.PUBLIC: frozenset({Permission.VIEW_DEMO}),
    Role.HOUSEHOLD: frozenset(
        {Permission.VIEW_DEMO, Permission.RUN_OPTIMISER, Permission.VIEW_OWN_REPORTS}
    ),
    Role.COMMUNITY_MANAGER: frozenset(
        {Permission.VIEW_DEMO, Permission.VIEW_COMMUNITY_REPORTS}
    ),
    Role.ANALYST: frozenset(
        {
            Permission.VIEW_DEMO,
            Permission.RUN_OPTIMISER,
            Permission.VIEW_OWN_REPORTS,
            Permission.VIEW_COMMUNITY_REPORTS,
            Permission.MANAGE_TARIFFS,
            Permission.INSPECT_DATA_QUALITY,
        }
    ),
    Role.ADMIN: _ALL,
}

# Which permission a page requires (None = always visible). Drives role-based
# page visibility in the app's st.navigation.
PAGE_PERMISSIONS: dict[str, Permission | None] = {
    "Home": None,
    "Methodology": None,
    "Add Tasks": Permission.RUN_OPTIMISER,
    "Optimise": Permission.RUN_OPTIMISER,
    "Compare": Permission.VIEW_OWN_REPORTS,
    "Community": Permission.VIEW_COMMUNITY_REPORTS,
    "Reports": Permission.VIEW_OWN_REPORTS,
    "Admin": Permission.MANAGE_USERS,
}


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]


def can(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def visible_pages(role: Role) -> list[str]:
    """Pages a role may see, in declaration order."""
    return [
        page
        for page, needed in PAGE_PERMISSIONS.items()
        if needed is None or can(role, needed)
    ]
