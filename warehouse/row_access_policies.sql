-- Warehouse-level enforcement: Snowflake row-access policies that mirror the
-- application scoping in src/community_energy_flex/auth/scoping.py. Defence in
-- depth - even a direct SQL connection cannot read another household's rows.
--
-- Run after warehouse/snowflake_setup.sql and a dbt build. Requires a role that
-- can create row-access policies (e.g. SECURITYADMIN or the object owner).

USE DATABASE ENERGY_FLEXIBILITY_OS;

-- Maps a Snowflake login (populated from OIDC/SSO, matched by CURRENT_USER())
-- to a role and the household/community it may see. Populated by the app's
-- user-management (admin) flow.
CREATE TABLE IF NOT EXISTS APP.USER_ACCESS (
    user_name       STRING,   -- matches CURRENT_USER()
    role            STRING,   -- public | household | community_manager | analyst | admin
    household_id    STRING,   -- for role = household
    community_key   NUMBER    -- for role = community_manager
);

-- Access rule, mirroring auth.scoping.scope_rows:
--   analyst / admin      -> all rows
--   household            -> own household_id only
--   community_manager    -> own community only
--   anyone else / public -> no rows
CREATE OR REPLACE ROW ACCESS POLICY APP.SAVINGS_ACCESS
    AS (household_id STRING, community_key NUMBER) RETURNS BOOLEAN ->
    EXISTS (
        SELECT 1
        FROM APP.USER_ACCESS ua
        WHERE ua.user_name = CURRENT_USER()
          AND (
                ua.role IN ('analyst', 'admin')
             OR (ua.role = 'household' AND ua.household_id = household_id)
             OR (ua.role = 'community_manager' AND ua.community_key = community_key)
          )
    );

-- Attach the policy to the fact. Household reports read only their own rows;
-- community managers only their community's; everyone else nothing.
ALTER TABLE MARTS.FCT_DAILY_SAVINGS
    ADD ROW ACCESS POLICY APP.SAVINGS_ACCESS ON (household_id, community_key);

-- To remove during development:
-- ALTER TABLE MARTS.FCT_DAILY_SAVINGS DROP ROW ACCESS POLICY APP.SAVINGS_ACCESS;
