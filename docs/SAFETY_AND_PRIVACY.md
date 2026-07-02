# Safety and privacy

## Safety statement

> This tool provides planning recommendations only. It does not directly control
> appliances, guarantee savings, or replace official energy, safety, or supplier
> advice.

## Why energy schedules are sensitive

Even simple schedules can reveal when people are home, daily routines, appliance
ownership, likely income level, EV ownership, and work patterns.

## Rules

- Store only what is needed.
- Community managers see **aggregated** reports only — never another household's
  detail.
- Allow export and deletion of user-entered data.
- Keep demo mode separate from real mode.
- Never claim guaranteed savings; show caveats on every recommendation.
- Do not shame high-energy users.

## RBAC — enforced in two layers

Access control is enforced by the tested `auth/` package (row-level scoping +
permission gate + audit trail) and, at the warehouse, by Snowflake row-access
policies — so a household never sees another household's data, even via a direct
SQL connection. Full model, roles, and OIDC config: [RBAC_MODEL.md](RBAC_MODEL.md).

> [!NOTE]
> The application scoping and audit are enforced and tested today. The Snowflake
> row-access policies and OIDC login are written and documented; they activate
> once a Snowflake account and identity provider are connected. Until then, run
> the app as single-tenant demo software.
