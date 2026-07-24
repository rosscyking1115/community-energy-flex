-- Domain-constraint test: the options mart must cover all 48 half-hour slots
-- exactly once, with no gaps. Returns a row (failing the test) if not.
with counts as (
    select planning_date, count(*) as n, count(distinct slot_index) as n_distinct,
           min(slot_index) as lo, max(slot_index) as hi
    from {{ ref('fct_half_hourly_energy_options') }}
    where source_promises_full_day
    group by planning_date
)
select * from counts
where n <> 48 or n_distinct <> 48 or lo <> 0 or hi <> 47
