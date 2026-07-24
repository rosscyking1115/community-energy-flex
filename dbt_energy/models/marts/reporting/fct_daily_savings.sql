-- The single fact table: one row per date x community x household x device, at a
-- consistent grain, with integer surrogate FKs to the dimensions. Power BI
-- imports this plus the dims and joins on the keys (a clean star, not a flat
-- wide table).
{{ config(contract={'enforced': true}) }}

with s as (
    select * from {{ ref('stg_daily_savings') }}
), grouped as (
    select
        savings_date,
        community_id,
        household_id,
        device_type,
        max(schedule_run_id) as schedule_run_id,
        bool_and(reporting_status = 'reportable') as all_source_rows_reportable,
        bool_and(
            preferred_start_index is not null
            and baseline_start_index = preferred_start_index
        ) as all_preferred_baselines_match,
        max(input_provenance_state) as input_provenance_state,
        max(fallback_reason) as fallback_reason,
        max(carbon_source) as carbon_source,
        max(carbon_source_label) as carbon_source_label,
        max(price_source) as price_source,
        max(price_source_label) as price_source_label,
        max(source_observed_at) as source_observed_at,
        max(source_valid_from) as source_valid_from,
        max(source_valid_to) as source_valid_to,
        bool_and(source_promises_full_day) as source_promises_full_day,
        bool_or(schedule_adherence_observed) as schedule_adherence_observed,
        max(preferred_start_index) as preferred_start_index,
        max(baseline_start_index) as baseline_start_index,
        max(scheduled_start_index) as scheduled_start_index,
        max(duration_slots) as duration_slots,
        count(*) as source_task_count,
        sum(baseline_cost_p) as raw_baseline_cost_p,
        sum(scheduled_cost_p) as raw_scheduled_cost_p,
        sum(baseline_carbon_g) as raw_baseline_carbon_g,
        sum(scheduled_carbon_g) as raw_scheduled_carbon_g,
        sum(baseline_peak_slot_count) as raw_baseline_peak_slot_count,
        sum(scheduled_peak_slot_count) as raw_scheduled_peak_slot_count,
        avg(robustness_score) as robustness_score,
        min(robustness_band) as robustness_band,
        count(distinct schedule_run_id) as schedule_run_count,
        count(distinct input_provenance_state) as provenance_count,
        count(distinct source_observed_at) as source_observed_count,
        count(distinct source_valid_from) as source_valid_from_count,
        count(distinct source_valid_to) as source_valid_to_count
    from s
    group by 1, 2, 3, 4
    having count(distinct schedule_run_id) = 1
       and count(distinct input_provenance_state) = 1
       and count(distinct source_observed_at) <= 1
       and count(distinct source_valid_from) <= 1
       and count(distinct source_valid_to) <= 1
), reportability as (
    select *,
        case when all_source_rows_reportable
            and all_preferred_baselines_match
            then 'reportable' else 'not_reportable' end as reporting_status
    from grouped
)
select
    d.date_key,
    dev.device_key,
    com.community_key,
    s.household_id,
    s.schedule_run_id,
    s.reporting_status,
    s.input_provenance_state,
    s.fallback_reason,
    s.carbon_source,
    s.carbon_source_label,
    s.price_source,
    s.price_source_label,
    s.source_observed_at,
    s.source_valid_from,
    s.source_valid_to,
    s.source_promises_full_day,
    s.schedule_adherence_observed,
    case when s.reporting_status = 'reportable' then s.preferred_start_index end as preferred_start_index,
    case when s.reporting_status = 'reportable' then s.baseline_start_index end as baseline_start_index,
    case when s.reporting_status = 'reportable' then s.scheduled_start_index end as scheduled_start_index,
    case when s.reporting_status = 'reportable' then s.duration_slots end as duration_slots,
    s.source_task_count,
    case when s.reporting_status = 'reportable' then s.raw_baseline_cost_p end as baseline_cost_p,
    case when s.reporting_status = 'reportable' then s.raw_scheduled_cost_p end as scheduled_cost_p,
    case when s.reporting_status = 'reportable' then s.raw_baseline_carbon_g end as baseline_carbon_g,
    case when s.reporting_status = 'reportable' then s.raw_scheduled_carbon_g end as scheduled_carbon_g,
    case when s.reporting_status = 'reportable'
        then cast(s.raw_baseline_peak_slot_count as integer) end as baseline_peak_slot_count,
    case when s.reporting_status = 'reportable'
        then cast(s.raw_scheduled_peak_slot_count as integer) end as scheduled_peak_slot_count,
    case when s.reporting_status = 'reportable'
        then s.raw_baseline_cost_p - s.raw_scheduled_cost_p end as reported_cost_saving_p,
    case when s.reporting_status = 'reportable'
        then s.raw_baseline_carbon_g - s.raw_scheduled_carbon_g end as reported_carbon_saving_g,
    case when s.reporting_status = 'reportable'
        then cast(s.raw_baseline_peak_slot_count - s.raw_scheduled_peak_slot_count as integer)
        end as reported_peak_slots_avoided,
    s.robustness_score,
    s.robustness_band
from reportability s
join {{ ref('dim_date') }} d        on d.full_date = s.savings_date
join {{ ref('dim_device') }} dev     on dev.device_type = s.device_type
join {{ ref('dim_community') }} com   on com.community_id = s.community_id
