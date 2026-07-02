"""The authorisation gate: check a permission and record the attempt.

This is the single choke point actions should go through - it both enforces the
permission and leaves an audit trail, so a denied attempt is logged, not silent.
"""

from __future__ import annotations

from community_energy_flex.auth.audit import AuditEvent, CsvAuditLog
from community_energy_flex.auth.roles import Permission, can
from community_energy_flex.auth.scoping import AccessDenied, User


def authorize(
    user: User,
    permission: Permission,
    resource: str,
    *,
    audit: CsvAuditLog | None = None,
    detail: str = "",
) -> None:
    """Allow the action or raise :class:`AccessDenied`, recording either way."""
    allowed = can(user.role, permission)
    if audit is not None:
        audit.record(
            AuditEvent(
                user_id=user.user_id,
                role=str(user.role),
                action=str(permission),
                resource=resource,
                allowed=allowed,
                detail=detail,
            )
        )
    if not allowed:
        raise AccessDenied(
            f"user '{user.user_id}' (role {user.role}) denied '{permission}' on '{resource}'"
        )
