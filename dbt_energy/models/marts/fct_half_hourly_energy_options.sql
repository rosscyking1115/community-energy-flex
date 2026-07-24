-- One row per half-hour slot with the cost and carbon of running 1 kWh then.
-- This is the raw material the optimiser scores over: cheapest / greenest slots
-- fall straight out of ordering this table.
with carbon as (
    select * from {{ ref('stg_carbon_intensity') }}
),
tariff as (
    select * from {{ ref('stg_tariff_rates') }}
)
select
    carbon.planning_date,
    carbon.slot_index,
    carbon.carbon_gco2_per_kwh,
    tariff.unit_rate_p_per_kwh,
    carbon.carbon_gco2_per_kwh   as carbon_per_kwh_gco2,
    tariff.unit_rate_p_per_kwh   as cost_per_kwh_p,
    case when carbon.slot_index between 34 and 37 then true else false end as is_peak_slot,
    carbon.source_observed_at,
    carbon.input_provenance_state,
    carbon.source_promises_full_day
from carbon
join tariff using (planning_date, slot_index)
order by carbon.planning_date, carbon.slot_index
