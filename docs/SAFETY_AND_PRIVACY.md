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

## RBAC — honest scope

> [!WARNING]
> The MVP's Streamlit role handling is **presentation-level only** (it hides
> pages/data by role in session state). It is *not* a security boundary and does
> not enforce cross-household isolation. Real isolation arrives in Milestone D
> with OIDC login, Snowflake row-access policies, and audit logging. Until then,
> do not treat multi-household separation as guaranteed.
