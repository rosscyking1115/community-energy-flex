-- Fixed fixture: prove dbt reports only the explicit preferred-start comparison.
with fixture as (
    select * from {{ ref('fct_daily_savings') }}
    where schedule_run_id = 'fixture-run-001'
), invalid_fixture as (
    select * from fixture
    where reporting_status <> 'reportable'
       or preferred_start_index <> 34
       or baseline_start_index <> 34
       or scheduled_start_index <> 0
       or baseline_cost_p <> 40.0 or scheduled_cost_p <> 20.0
       or baseline_carbon_g <> 600.0 or scheduled_carbon_g <> 200.0
       or reported_cost_saving_p <> 20.0
       or reported_carbon_saving_g <> 400.0
       or reported_peak_slots_avoided <> 2
), invalid_preferred_start_rows as (
    select * from {{ ref('fct_daily_savings') }}
    where schedule_run_id in (
        'fixture-run-missing-preferred',
        'fixture-run-clamped-preferred',
        'fixture-run-mixed-preferred'
    )
      and (
        reporting_status <> 'not_reportable'
        or reported_cost_saving_p is not null
        or reported_carbon_saving_g is not null
        or reported_peak_slots_avoided is not null
      )
)
select 'fixed_fixture_reconciliation' as failure, count(*) as failure_count from invalid_fixture
having count(*) > 0
union all
select 'missing_or_clamped_preferred_start_must_not_report' as failure, count(*) as failure_count
from invalid_preferred_start_rows
having count(*) > 0
