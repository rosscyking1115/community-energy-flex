# Forecast-vintage archive

**Started and stopped 2026-07-27.** A capture job, not a product. It has no app, no
API, and no dashboard, and it is not part of the Community Energy Flex product
surface — that surface is frozen (see [STATUS](../../docs/STATUS.md)).

> ## Collection is stopped
>
> **Held: 10 vintages, 18,240 rows, 2026-07-27 15:35Z to 22:05Z, no gaps, no failures.**
> That is roughly six and a half hours of coverage and is not enough for any
> evaluation.
>
> It was stopped the day it started because **nothing consumes it**: no code reads the
> data, and the only claims that mention it assert that it exists and has produced no
> result. An hourly job on a personal laptop is a cost with no return, and the honest
> response to that is to stop rather than to move it somewhere cheaper and let it
> accumulate unread.
>
> **Restarting** is one command plus one scheduled task (below), and costs only the
> hours between. Before restarting, name the artefact that will consume it — the
> reason to keep this running is a named consumer, not the fact that the data is
> perishable. Perishability is why it must not be *paused indefinitely while
> pretending to collect*; it is not on its own a reason to collect.
>
> What was measured while it ran is recorded under
> [Measured, 2026-07-27](#measured-2026-07-27) and
> [Timing sensitivity](#timing-sensitivity), so a future restart does not have to
> rediscover it.

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

## Timing sensitivity

Measured across the 10 captures held, because it decides where a restarted job should
run and it would otherwise have to be rediscovered.

**Delay does not corrupt the data.** `observed_at` is taken from the wall clock at
capture, not from the schedule, so a late run records a *correct* timestamp at an
irregular interval rather than a wrong one at a regular one. Every capture spans the
full 47.4-hour horizon regardless of when it fired — verified across captures spaced
2.6 minutes apart and 60 minutes apart, all yielding 1,824 rows and the same horizon
range. A scheduler that fires late therefore loses nothing. A scheduler that **drops**
a run loses that vintage permanently. Those are very different failures and only the
second one matters.

**The forecast republishes somewhere between 18 and 60 minutes.** Comparing every
shared target period between consecutive captures:

| Interval | Values changed |
|---|---|
| 2.6 min | 0 of 1,824 (0.0%) |
| 8.5 min | 0 of 1,824 (0.0%) |
| 18.2 min | 0 of 1,805 (0.0%) |
| 60 min | 1,027–1,434 of 1,786 (57.5%–80.3%) |

So captures less than ~20 minutes apart are pure duplication, and **hourly capture was
already under-sampling** — well over half the values moved between one capture and the
next, meaning intermediate vintages were being missed. A restart should use half-hourly
to match the settlement period, at roughly 155 MB/year.

**No credentials are required.** Every request made against
`api.carbonintensity.org.uk` while building and running this was unauthenticated. There
is no secret to manage and no key to rotate.

**If it is ever restarted, host it on a scheduled CI runner rather than a laptop.** A
laptop that is asleep at the scheduled minute silently drops the run, which is the one
failure that costs data. Scheduled CI is not punctual — runs queue, and can be dropped
under load — but the measurements above show delay is harmless here and only drops
hurt, so the trade favours the runner. Two hazards come with it, and neither is
optional:

- On a **public** repository, GitHub disables scheduled workflows after 60 days without
  repository activity. A quiet repo stops collecting silently.
- **A stall detector must not live inside the thing it monitors.** A disabled workflow
  cannot report its own death, and `continuity` returning exit 2 is worthless if
  nothing runs it. Any restart needs the staleness check running somewhere independent
  of the capture job, reading the manifest and failing loudly.

## Running it

```bash
pip install -e ".[archive]"
python -m research.forecast_vintages.capture
```

Every attempt — including every failure — is appended to `data/manifest.jsonl`, so a
gap in the evidence is recorded rather than silently absent.

It ran hourly as the Windows task `CEF-ForecastVintageCapture`, now unregistered.
Nothing is scheduled. To restart on this machine — read
[Timing sensitivity](#timing-sensitivity) first, which argues against a laptop and
for half-hourly:

```powershell
$repo = 'C:\dev\portfolio\community-energy-flex'
$action = New-ScheduledTaskAction -Execute (Join-Path $repo '.venv\Scripts\python.exe') `
  -Argument '-m research.forecast_vintages.capture' -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName 'CEF-ForecastVintageCapture' `
  -Action $action -Trigger $trigger -Force
```

The working directory must be the repository, which is what makes
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

The daily task `CEF-ForecastVintageBackup` was unregistered alongside the capture job;
the OneDrive copy remains and holds all 10 vintages. The copy
is incremental (Parquet files are immutable once written, so a size match counts as
present; the manifest grows and is always refreshed) and **additive only** — it
never deletes at the destination, because a bug in a backup tool should not be able
to destroy the one thing that cannot be recreated.

**OneDrive is sync, not versioned backup.** It protects against losing this machine.
It does not protect against corruption, because a corrupted local file syncs upward
and overwrites the good copy — the failure propagates rather than being contained.
Parquet files here are immutable once written, which narrows the exposure to the
manifest and to disk-level corruption, but it does not remove it.

The versioned copy is elsewhere. An encrypted, versioned, off-site **restic**
repository exists and is verified: `b2:ross-files-backup:files-backup` on Backblaze
B2, restic 0.19.0, 12 snapshots, 41.6 GiB, with backup, prune and check all clean on
its last successful run and `check` reporting no errors found. **Verified 2026-07-23;
recorded here 2026-07-28.** The OneDrive mirror is therefore a second, unversioned
copy rather than the only one.

Do not build a third mechanism. If either of the two above appears to be missing,
check whether it has merely stopped running before concluding it does not exist — and
re-date this paragraph when you check, because a backup claim with no verification
date is the failure mode that put a false statement here in the first place.

## What this does not do

It does not evaluate anything yet, and it makes no claim about forecast quality. It
accumulates the evidence that an evaluation would need. Until there are enough
vintages to cover a range of horizons and seasons, there is nothing to conclude and
this directory should not be described as a result.

`data/` is git-ignored: the archive is local and reproducible only going forward,
never by re-running history.
