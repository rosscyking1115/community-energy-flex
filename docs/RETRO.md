# Forecast-vs-actual retro loop

> "Did yesterday's plan actually save?"

Most tools stop at a *prediction* — "run this load then, save this much." This one
closes the loop. A schedule is committed on the carbon **forecast**; once the day
has passed, the Carbon Intensity API exposes the measured **actual**, and the same
fixed plan is re-scored against what really happened. That turns *"we think this
saves"* into *evidence*, and it surfaces how good the forecast was.

The engine is [`src/community_energy_flex/monitoring/retro.py`](../src/community_energy_flex/monitoring/retro.py):
`evaluate_retrospective()` re-scores each task's committed slot against the actual
curve and returns the realised saving, plus the forecast error (MAE and bias).

## Worked demo

One plan (four community-centre loads, **491 g CO₂** saving expected), re-scored
against several ways the day could actually turn out:

| How the day turned out | Forecast | Actual | Realised | Forecast MAE | Still saved? |
|---|--:|--:|--:|--:|:-:|
| Forecast was spot on | 491 g | 491 g | 100% | 0 g | yes |
| Grid ran 8% dirtier | 491 g | 530 g | **108%** | 16 g | yes |
| Grid ran 6% cleaner | 491 g | 461 g | 94% | 12 g | yes |
| Noisy day (±15%) | 491 g | 518 g | 106% | 15 g | yes |
| Evening peak came 1h late | 491 g | 332 g | **68%** | 20 g | yes |

**Across the five scenarios: 95% of the forecast carbon saving realised on
average; the plan still saved carbon in 5/5.**

## Reading it honestly

- **108% when the grid ran dirtier** isn't a bug: shifting *away from* a
  dirtier-than-expected peak avoids more carbon in absolute terms. The plan gets
  *more* valuable exactly when the day is worse than forecast.
- **68% when the evening peak arrived an hour late** is the honest failure mode:
  a *structural* forecast miss (wrong shape, not just wrong level) is what erodes
  the saving. It still saved — but this is the case a confidence band should, and
  does, flag as lower-confidence.
- **Cost is unchanged in every row.** Agile prices are published day-ahead, so the
  only thing the forecast can get wrong is **carbon** — which is precisely what
  this table stresses.

## Reproduce

```bash
PYTHONPATH=src python scripts/retro_demo.py
```

> The actuals here are **simulated** to exercise the loop — the forecast made on a
> past day isn't stored, so a true historical replay isn't possible. The retro
> maths is the real engine; only the "actual" curves are synthetic. See
> [CASE_STUDY.md](CASE_STUDY.md) for the single-day version with real optimiser
> output.
