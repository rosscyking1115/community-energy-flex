-- Singular test: cost and carbon can never be negative. Returns offending rows
-- (dbt passes when the query returns none).
select slot_index, cost_per_kwh_p, carbon_gco2_per_kwh
from {{ ref('fct_half_hourly_energy_options') }}
where cost_per_kwh_p < 0 or carbon_gco2_per_kwh < 0
