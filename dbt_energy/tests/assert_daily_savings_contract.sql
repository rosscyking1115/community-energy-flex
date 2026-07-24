-- The fact has one reporting row per date x community x household x device.
with duplicate_keys as (
    select date_key, community_key, household_id, device_key
    from {{ ref('fct_daily_savings') }}
    group by 1, 2, 3, 4
    having count(*) > 1
), aggregation_mismatch as (
    select
        s.savings_date,
        s.community_id,
        s.household_id,
        s.device_type,
        count(*) as expected_source_task_count,
        max(f.source_task_count) as actual_source_task_count
    from {{ ref('stg_daily_savings') }} s
    join {{ ref('dim_date') }} d on d.full_date = s.savings_date
    join {{ ref('dim_device') }} dev on dev.device_type = s.device_type
    join {{ ref('dim_community') }} com on com.community_id = s.community_id
    left join {{ ref('fct_daily_savings') }} f
        on f.date_key = d.date_key
        and f.device_key = dev.device_key
        and f.community_key = com.community_key
        and f.household_id = s.household_id
    group by 1, 2, 3, 4
    having max(f.source_task_count) is distinct from count(*)
), invalid_reportable_rows as (
    select *
    from {{ ref('fct_daily_savings') }}
    where reporting_status = 'reportable'
      and (
        source_observed_at is null
        or source_valid_from is null
        or source_valid_to is null
        or baseline_cost_p is null or scheduled_cost_p is null
        or preferred_start_index is null
        or baseline_start_index <> preferred_start_index
        or baseline_carbon_g is null or scheduled_carbon_g is null
        or baseline_peak_slot_count is null or scheduled_peak_slot_count is null
        or reported_cost_saving_p is null or reported_carbon_saving_g is null
        or reported_peak_slots_avoided is null
        or baseline_cost_p < 0 or scheduled_cost_p < 0
        or baseline_carbon_g < 0 or scheduled_carbon_g < 0
        or baseline_peak_slot_count < 0 or scheduled_peak_slot_count < 0
        or source_task_count < 1
      )
), invalid_differences as (
    select *
    from {{ ref('fct_daily_savings') }}
    where reporting_status = 'reportable'
      and (
        reported_cost_saving_p <> baseline_cost_p - scheduled_cost_p
        or reported_carbon_saving_g <> baseline_carbon_g - scheduled_carbon_g
        or reported_peak_slots_avoided <> baseline_peak_slot_count - scheduled_peak_slot_count
        or reported_peak_slots_avoided > baseline_peak_slot_count
      )
), invalid_non_reportable_rows as (
    select *
    from {{ ref('fct_daily_savings') }}
    where reporting_status = 'not_reportable'
      and (
        reported_cost_saving_p is not null
        or reported_carbon_saving_g is not null
        or reported_peak_slots_avoided is not null
      )
), mixed_lineage_at_reporting_grain as (
    select savings_date, community_id, household_id, device_type
    from {{ ref('stg_daily_savings') }}
    group by 1, 2, 3, 4
    having count(distinct schedule_run_id) > 1
        or count(distinct input_provenance_state) > 1
        or count(distinct source_observed_at) > 1
        or count(distinct source_valid_from) > 1
        or count(distinct source_valid_to) > 1
)
select 'duplicate_reporting_key' as failure, count(*) as failure_count from duplicate_keys
having count(*) > 0
union all
select 'staging_rows_not_aggregated_to_reporting_grain' as failure, count(*) as failure_count from aggregation_mismatch
having count(*) > 0
union all
select 'missing_reportable_input_or_difference' as failure, count(*) as failure_count from invalid_reportable_rows
having count(*) > 0
union all
select 'difference_or_peak_bound' as failure, count(*) as failure_count from invalid_differences
having count(*) > 0
union all
select 'non_reportable_values_must_remain_null' as failure, count(*) as failure_count from invalid_non_reportable_rows
having count(*) > 0
union all
select 'mixed_lineage_at_reporting_grain' as failure, count(*) as failure_count from mixed_lineage_at_reporting_grain
having count(*) > 0
