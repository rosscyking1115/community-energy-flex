-- Half-hourly unit rates, one row per slot. Standing charge is carried through
-- but deliberately NOT used in savings (it is fixed per day).
with src as (
    select * from {{ ref('seed_tariff_rates') }}
)
select
    cast('2026-07-04' as date) as planning_date,
    cast(slot_index as integer)             as slot_index,
    cast(unit_rate_p_per_kwh as double)     as unit_rate_p_per_kwh,
    'sample_input' as input_provenance_state,
    true as source_promises_full_day
from src
