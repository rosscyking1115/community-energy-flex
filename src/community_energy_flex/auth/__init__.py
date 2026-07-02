"""Authentication and authorisation.

Two layers enforce the privacy promises (see docs/RBAC_MODEL.md):

1. **Application-level** - the tested logic here: role -> permissions
   (:mod:`roles`), row-level data scoping (:mod:`scoping`), an audit trail
   (:mod:`audit`), and the :func:`~community_energy_flex.auth.service.authorize`
   gate that ties permission checks to the audit log.
2. **Warehouse-level** - Snowflake row-access policies
   (``warehouse/row_access_policies.sql``), so even a direct SQL connection
   cannot read another household's rows.

The MVP's Streamlit session RBAC is presentation-only; this package is what makes
access control actually enforced.
"""

from community_energy_flex.auth.audit import AuditEvent, CsvAuditLog
from community_energy_flex.auth.roles import (
    Permission,
    Role,
    can,
    permissions_for,
    visible_pages,
)
from community_energy_flex.auth.scoping import AccessDenied, User, require, scope_rows
from community_energy_flex.auth.service import authorize

__all__ = [
    "Role",
    "Permission",
    "permissions_for",
    "can",
    "visible_pages",
    "User",
    "AccessDenied",
    "scope_rows",
    "require",
    "AuditEvent",
    "CsvAuditLog",
    "authorize",
]
