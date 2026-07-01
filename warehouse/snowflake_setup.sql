-- Snowflake bootstrap for Community Energy Flexibility OS.
-- Run once as a role that can create databases/warehouses (e.g. SYSADMIN).
-- The dbt project (target: snowflake) then builds STAGING/MARTS on top.

CREATE DATABASE IF NOT EXISTS ENERGY_FLEXIBILITY_OS;

USE DATABASE ENERGY_FLEXIBILITY_OS;

CREATE SCHEMA IF NOT EXISTS RAW;           -- source loads (carbon, tariffs, constraints)
CREATE SCHEMA IF NOT EXISTS STAGING;       -- dbt staging views
CREATE SCHEMA IF NOT EXISTS MARTS;         -- dbt marts (facts/dims/reporting)
CREATE SCHEMA IF NOT EXISTS OPTIMISATION;  -- optimiser outputs
CREATE SCHEMA IF NOT EXISTS MONITORING;    -- pipeline runs, optimisation quality, freshness
CREATE SCHEMA IF NOT EXISTS APP;           -- app-facing tables (users, roles)
CREATE SCHEMA IF NOT EXISTS REPORTING;     -- Power BI / export tables

-- A small, auto-suspending warehouse is plenty for this data volume
-- (~670 rows/day). Keep costs near zero.
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
  WAREHOUSE_SIZE = XSMALL
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- Monitoring tables mirror community_energy_flex.monitoring.store records.
CREATE TABLE IF NOT EXISTS MONITORING.PIPELINE_RUNS (
    run_id STRING, job STRING, status STRING, duration_s FLOAT,
    rows_ingested INTEGER, message STRING, recorded_at TIMESTAMP_TZ
);

CREATE TABLE IF NOT EXISTS MONITORING.OPTIMISATION_QUALITY (
    run_id STRING, objective STRING, task_count INTEGER,
    total_cost_saving_p FLOAT, total_carbon_saving_g FLOAT,
    avg_confidence FLOAT, constraint_violations INTEGER, recorded_at TIMESTAMP_TZ
);

CREATE TABLE IF NOT EXISTS MONITORING.DATA_FRESHNESS (
    run_id STRING, source STRING, fetched_at TIMESTAMP_TZ,
    expected_slots INTEGER, actual_slots INTEGER, is_fresh BOOLEAN,
    recorded_at TIMESTAMP_TZ
);
