-- Half-hourly carbon intensity, one row per slot (0..47).
with src as (
    select * from {{ ref('seed_carbon_intensity') }}
)
select
    cast('2026-07-04' as date) as planning_date,
    cast(slot_index as integer)                as slot_index,
    cast(forecast_gco2_per_kwh as double)      as carbon_gco2_per_kwh,
    cast(data_fetched_at as timestamp) as source_observed_at,
    'sample_input' as input_provenance_state,
    true as source_promises_full_day
from src
