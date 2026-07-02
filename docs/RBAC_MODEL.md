# Roles, access control, and auth

Access control is enforced in **two layers** so the privacy promises in
[SAFETY_AND_PRIVACY.md](SAFETY_AND_PRIVACY.md) are real, not aspirational.

## Roles and permissions

| Role | Sees | Key permissions |
|---|---|---|
| **Public** | Demo data only | `view_demo` |
| **Household** | Own tasks, own optimiser, own reports | `run_optimiser`, `view_own_reports` |
| **Community manager** | Aggregated reports for their community | `view_community_reports` |
| **Analyst** | All data; manages tariffs; inspects data quality | + `manage_tariffs`, `inspect_data_quality` |
| **Admin** | Everything, plus users/roles and pipeline | all permissions |

The full matrix lives in code: `src/community_energy_flex/auth/roles.py`
(`ROLE_PERMISSIONS`). `visible_pages(role)` drives role-based page visibility in
the app.

## Layer 1 — application (enforced, tested)

`src/community_energy_flex/auth/`:

- **`scoping.py`** — `scope_rows(user, rows)` returns only the rows a user may
  see: household → own `household_id`; community manager → own `community_id`;
  analyst/admin → all; public → none. `require(user, permission)` raises
  `AccessDenied`.
- **`service.py`** — `authorize(user, permission, resource, audit=...)` is the
  single choke point: it enforces the permission **and** records the attempt.
- **`audit.py`** — every allowed/denied decision is appended to an audit log.

This is covered by `tests/test_auth.py` (household can't see other households,
public sees nothing, denied attempts raise and are logged).

## Layer 2 — warehouse (defence in depth)

`warehouse/row_access_policies.sql` attaches a Snowflake **row-access policy** to
`MARTS.FCT_DAILY_SAVINGS` that mirrors the application rule, keyed on
`CURRENT_USER()` via the `APP.USER_ACCESS` map. So even a direct SQL connection
(bypassing the app) cannot read another household's rows.

## Authentication

- **Production:** OIDC via Streamlit's native `st.login()` / `st.user`. Configure
  an identity provider (Google/Microsoft) in `.streamlit/secrets.toml`:

  ```toml
  [auth]
  redirect_uri = "https://your-app/oauth2callback"
  cookie_secret = "..."
  client_id = "..."
  client_secret = "..."
  server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
  ```

  The login email maps to a `Role` (and household/community) via a user table
  the admin manages; that same mapping populates `APP.USER_ACCESS` for Layer 2.

- **Local / demo:** no secrets required — the app offers a role picker so the
  RBAC behaviour can be explored without an identity provider. Demo mode is kept
  separate from real data (public role sees only sample data).

## Honest scope

Application scoping + audit are enforced and tested today. The Snowflake policies
and OIDC are configured and documented; they activate once a Snowflake account
and identity provider are connected. Until then, treat the app as single-tenant
demo software, not a hardened multi-tenant deployment.
