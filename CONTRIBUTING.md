# Contributing

Thanks for your interest in Community Energy Flex. Bug reports, docs,
tariff/region support, and optimiser improvements are all welcome.

## Ground rules

- **Be useful and honest.** Recommendations must show their assumptions and
  caveats and never claim guaranteed savings
  (see [docs/PRODUCT_THESIS.md](docs/PRODUCT_THESIS.md)).
- **Keep the core dependency-light.** `src/community_energy_flex/` runs on the
  standard library; Streamlit, dbt, Dagster, PuLP, MLflow, and report writers are
  all optional extras behind guarded imports.
- **Respect privacy.** Don't weaken the access-control model
  ([docs/RBAC_MODEL.md](docs/RBAC_MODEL.md)) or log household-level data.

## Development setup

```bash
python -m pip install -e ".[dev]"     # core + pytest + ruff
python -m pytest                       # full suite
ruff check .                           # lint (also runs in CI)
```

Optional extras when working on those areas: `app` (Streamlit), `reports`
(Excel/PDF), `warehouse` (dbt-duckdb), `snowflake`, `optim` (PuLP), `orchestration`
(Dagster), `tracking` (MLflow). See [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Making a change

1. Branch off `main`.
2. **Write a test first** where it makes sense — the optimiser is correctness-
   critical, so its invariants live in `tests/` (optimised cost ≤ baseline for
   `cheapest`, all `must_run` tasks scheduled, nothing outside its feasible window).
   Assert against independently worked-out expected values, not the solver's own
   output.
3. Keep functions deep and I/O injected (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md));
   the Streamlit app can be smoke-tested headlessly with `streamlit.testing.v1.AppTest`.
4. Run `python -m pytest` and `ruff check .` — both must pass. CI runs them on
   Python 3.11–3.13.
5. Open a PR describing the change and the reasoning. Update the relevant `docs/`
   page if behaviour changes.

## Reporting bugs

Open an issue with what you did, what you expected, and what happened. For
optimiser/reporting issues, include the tasks, tariff, and objective so it can be
reproduced.

## Conventions

- Formatting/lint: `ruff` (config in `pyproject.toml`).
- British English in user-facing copy and docs.
- Prefer generalising a mechanism over adding special cases.
