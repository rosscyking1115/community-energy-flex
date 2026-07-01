-- Half-hourly unit rates, one row per slot. Standing charge is carried through
-- but deliberately NOT used in savings (it is fixed per day).
with src as (
    select * from {{ ref('seed_tariff_rates') }}
)
select
    cast(slot_index as integer)             as slot_index,
    cast(unit_rate_p_per_kwh as double)     as unit_rate_p_per_kwh
from src
