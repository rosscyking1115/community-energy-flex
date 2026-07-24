-- Cleaned per-task daily savings (optimiser output). One row per
-- date x community x household x device.
with src as (
    select * from {{ ref('seed_daily_savings') }}
)
select
    cast(savings_date as date) as savings_date,
    cast(community_id as varchar) as community_id,
    cast(household_id as varchar) as household_id,
    cast(task_id as varchar) as task_id,
    cast(device_type as varchar) as device_type,
    cast(schedule_run_id as varchar) as schedule_run_id,
    cast(reporting_status as varchar) as reporting_status,
    cast(input_provenance_state as varchar) as input_provenance_state,
    nullif(cast(fallback_reason as varchar), '') as fallback_reason,
    cast(carbon_source as varchar) as carbon_source,
    cast(carbon_source_label as varchar) as carbon_source_label,
    cast(price_source as varchar) as price_source,
    cast(price_source_label as varchar) as price_source_label,
    cast(source_observed_at as timestamp) as source_observed_at,
    cast(source_valid_from as timestamp) as source_valid_from,
    cast(source_valid_to as timestamp) as source_valid_to,
    cast(source_promises_full_day as boolean) as source_promises_full_day,
    cast(schedule_adherence_observed as boolean) as schedule_adherence_observed,
    cast(preferred_start_index as integer) as preferred_start_index,
    cast(baseline_start_index as integer) as baseline_start_index,
    cast(scheduled_start_index as integer) as scheduled_start_index,
    cast(duration_slots as integer) as duration_slots,
    cast(baseline_cost_p as double) as baseline_cost_p,
    cast(scheduled_cost_p as double) as scheduled_cost_p,
    cast(baseline_carbon_g as double) as baseline_carbon_g,
    cast(scheduled_carbon_g as double) as scheduled_carbon_g,
    cast(baseline_peak_slot_count as integer) as baseline_peak_slot_count,
    cast(scheduled_peak_slot_count as integer) as scheduled_peak_slot_count,
    cast(robustness_score as double) as robustness_score,
    cast(robustness_band as varchar) as robustness_band
from src
