-- Reporting marts are strict aggregates of the daily fact, with no new formula.
with daily_expected as (
    select date_key,
        sum(reported_cost_saving_p) as total_cost_saving_p,
        sum(reported_carbon_saving_g) as total_carbon_saving_g,
        sum(reported_peak_slots_avoided) as peak_slots_avoided
    from {{ ref('fct_daily_savings') }}
    where reporting_status = 'reportable'
    group by 1
), daily_mismatch as (
    select r.* from {{ ref('rpt_daily_savings') }} r
    join daily_expected e using (date_key)
    where abs(r.total_cost_saving_p - e.total_cost_saving_p) > 0.000001
       or abs(r.total_carbon_saving_g - e.total_carbon_saving_g) > 0.000001
       or r.peak_slots_avoided <> e.peak_slots_avoided
)
select 'daily_aggregate_mismatch' as failure, count(*) as failure_count from daily_mismatch
having count(*) > 0
