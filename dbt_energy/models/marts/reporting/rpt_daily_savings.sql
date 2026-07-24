-- Pre-aggregated daily totals for the Cost/Carbon Timeline page.
select
    f.date_key,
    d.full_date,
    sum(f.reported_cost_saving_p)        as total_cost_saving_p,
    sum(f.reported_carbon_saving_g)      as total_carbon_saving_g,
    sum(f.reported_peak_slots_avoided)   as peak_slots_avoided,
    avg(f.robustness_score)     as avg_robustness,
    count(*)                    as task_count
from {{ ref('fct_daily_savings') }} f
join {{ ref('dim_date') }} d on d.date_key = f.date_key
where f.reporting_status = 'reportable'
group by f.date_key, d.full_date
