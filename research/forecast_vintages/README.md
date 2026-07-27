# Forecast-vintage archive

**Started 2026-07-27.** A capture job, not a product. It has no app, no API, and no
dashboard, and it is not part of the Community Energy Flex product surface — that
surface is frozen (see [STATUS](../../docs/STATUS.md)).

## The question

> **How wrong is the GB carbon-intensity forecast, by horizon, region and season?**

That is an honest-evaluation question with a measurable answer. Nobody has to want
a product for it to be worth answering, and answering it needs data that only
exists if someone starts keeping it.

## Why it had to start immediately

The GB Carbon Intensity API serves the *current* forecast, and for past periods it
serves a single settled forecast value. It does not serve what the forecast said at
a given moment in the past. So forecast vintages are **not reconstructable after
the fact**: every observation time that is not captured is gone permanently.

Verified on 2026-07-27 against the live API, rather than assumed:

1. **Every documented endpoint is keyed by target time, not issue time.** The
   published endpoint list (`carbon-intensity.github.io/api-definitions/`) contains
   27 intensity paths. All of them take `{from}`, `{to}`, `{date}`, `{period}` or a
   `fw*`/`pt*` window *relative to a target time*. None takes an issue time, an
   "as of", or a vintage.
2. **A past-dated forward window does not return the vintage issued then.** Asking
   `/intensity/2026-07-18T12:00Z/fw48h` returns, for every overlapping target
   period, exactly the same single forecast value as the plain historical
   `/intensity/{from}/{to}` endpoint — for example target `2026-07-20T00:30Z`
   returns `forecast=96, actual=107` from both. The forward window replays the
   settled series; it does not replay history.
3. **The issue time of the settled forecast is undocumented.** The archive holds
   one forecast number per settlement period and does not say when it was produced,
   so forecast error is visible but cannot be attributed to a horizon. The
   `96 vs 107` example above is a 11 gCO2/kWh miss at an unknown lead time, which
   is exactly the gap this archive is meant to close.

## What is stored

One row per (observation time × target period × region), written to Parquet
partitioned by capture date.

| Column | Meaning |
|---|---|
| `observed_at` | **Transaction time.** When *this job* read the value. |
| `target_from`, `target_to` | **Valid time.** The half-hour being forecast. |
| `horizon_minutes` | `target_from - observed_at`. Negative at the head of the window, where the period has already begun. |
| `region_id`, `region_shortname`, `dno_region` | DNO region; `region_id` is null for the GB national series. |
| `forecast_gco2_per_kwh` | The forecast as it stood at `observed_at`. |
| `actual_gco2_per_kwh` | Settled value where the API already has one; usually null in a forward window. |
| `intensity_index` | The provider's own band label. |

**`observed_at` is capture time, not publication time.** The API publishes no issue
timestamp, so `observed_at` is an *upper bound* on when the forecast was issued,
never the issue time itself. Any analysis built on this must say so; horizons
computed from it are horizons-from-observation, which is a slightly pessimistic
proxy for horizons-from-issue.

## Measured, 2026-07-27

| | |
|---|---|
| Rows per capture | 1,824 (19 series × 96 half-hourly periods) |
| Parquet bytes per capture | 8,847 (zstd) |
| Rows per day, hourly capture | 43,776 |
| Storage per year, hourly capture | ~78 MB |
| Storage per year, half-hourly capture | ~155 MB |

## Running it

```bash
pip install -e ".[archive]"
python -m research.forecast_vintages.capture
```

Every attempt — including every failure — is appended to `data/manifest.jsonl`, so a
gap in the evidence is recorded rather than silently absent.

**Scheduled on this machine since 2026-07-27**, hourly, as the Windows task
`CEF-ForecastVintageCapture`. Half-hourly would match the settlement period exactly
and double both resolution and storage.

```powershell
# inspect
Get-ScheduledTaskInfo -TaskName 'CEF-ForecastVintageCapture'
# remove
Unregister-ScheduledTask -TaskName 'CEF-ForecastVintageCapture' -Confirm:$false
```

The task runs with the repository as its working directory, which is what makes
`-m research.forecast_vintages.capture` resolve.

```bash
python -m research.forecast_vintages.continuity
```

Reports attempts, successes, failures, row counts and the gaps between successful
captures. Coverage is read from the manifest, never inferred from whichever files
happen to be on disk.

It also reports whether the archive is still collecting, which a gap check alone
cannot tell you: gaps only exist *between* successful captures, so a job that dies
and never returns leaves an unblemished record and a `last observed` that quietly
recedes. That is exactly how a scheduled task fails when its interpreter or working
directory moves. Exit code is `2` when stalled, `0` while collecting, so cron or a
monitor can act on it.

## Backup

Nothing can rebuild a vintage that was never captured, so a lost disk is a lost
archive. `data/` is mirrored to OneDrive — off this machine, because there is only
one physical drive here and a second local copy would protect against nothing.

```bash
python -m research.forecast_vintages.backup --dest "<path>"
```

Scheduled daily at 03:30 as the Windows task `CEF-ForecastVintageBackup`. The copy
is incremental (Parquet files are immutable once written, so a size match counts as
present; the manifest grows and is always refreshed) and **additive only** — it
never deletes at the destination, because a bug in a backup tool should not be able
to destroy the one thing that cannot be recreated.

## What this does not do

It does not evaluate anything yet, and it makes no claim about forecast quality. It
accumulates the evidence that an evaluation would need. Until there are enough
vintages to cover a range of horizons and seasons, there is nothing to conclude and
this directory should not be described as a result.

`data/` is git-ignored: the archive is local and reproducible only going forward,
never by re-running history.
