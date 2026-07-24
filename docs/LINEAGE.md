# Reporting lineage

```mermaid
flowchart LR
    F[Forecast acquisition\nlive, unavailable, sample] --> D[Dagster acquisition asset]
    D -->|accepted provenance| P[Python core\nvalidate and optimise]
    D -->|missing provenance or failure| L[Last-good schedule retained\noriginal run, provenance, timestamps, validity, failure reason]
    P --> S[Raw schedule and explicit preferred baseline]
    S --> R[Dagster action-report guard]
    R -->|success + live/sample provenance| A[Illustrative action report]
    R -->|fallback/failed/unavailable| B[Blocked fresh publication]
    S --> M[dbt reporting transformation]
    M --> BI[Power BI conditional metrics]
```

Dagster coordinates acquisition, core optimisation, reporting and last-good
behaviour. The optimiser and business rules remain in the tested Python core.
dbt owns reporting aggregation and reported differences. No Airflow is used,
and dbt is not invoked by Dagster because that would duplicate the existing
verified reporting build rather than improve lineage.

At the fixed reporting grain, dbt rejects mixed schedule-run, provenance, or
source-validity lineage rather than concatenating it into one field. A missing
or clamped preferred start is `not_reportable`, with all reported differences
`NULL`.
