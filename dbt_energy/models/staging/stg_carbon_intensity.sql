-- Half-hourly carbon intensity, one row per slot (0..47).
with src as (
    select * from {{ ref('seed_carbon_intensity') }}
)
select
    cast(slot_index as integer)                as slot_index,
    cast(forecast_gco2_per_kwh as double)      as carbon_gco2_per_kwh
from src
