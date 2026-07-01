"""Turn a recommendation into an honest confidence score and caveat.

Confidence is a product of four factors, each in (0, 1], so any single weak
input drags the result down (the plan's principle: *make uncertainty visible*):

* **decisiveness** - how much better the winner is than the *typical* option.
  Measured against the mean of all feasible options, not the adjacent
  runner-up (on a 48-slot day the next slot is always a near-tie, which would
  make every recommendation look fragile). A flat landscape where every time is
  equally good is honestly low-decisiveness: the choice barely matters.
* **horizon**       - forecasts further into the future are less reliable.
* **data**          - measured actual carbon beats a forecast.
* **tariff**        - a hand-typed tariff is less trustworthy than a known one.

The weakest factor drives the plain-language caveat.
"""

from __future__ import annotations

from dataclasses import dataclass

# How far the best option must beat the mean option (on the 0..1 objective
# scale) to count as fully decisive; smaller margins scale down proportionally.
_DECISIVE_MARGIN = 0.25
_DECISIVENESS_FLOOR = 0.3


@dataclass(frozen=True)
class Confidence:
    value: float
    band: str
    caveat: str


def _band(value: float) -> str:
    if value >= 0.75:
        return "High"
    if value >= 0.5:
        return "Medium"
    return "Low"


def compute_confidence(
    sorted_scores: list[float],
    *,
    horizon_hours: float,
    using_actual_carbon: bool,
    tariff_is_manual: bool,
    single_option: bool = False,
) -> Confidence:
    if single_option or len(sorted_scores) < 2:
        decisiveness = 0.6  # only one way to run it: neither strong nor weak
    else:
        best = sorted_scores[0]
        mean = sum(sorted_scores) / len(sorted_scores)
        materiality = mean - best  # >= 0 on the normalised 0..1 scale
        decisiveness = min(
            1.0, _DECISIVENESS_FLOOR
            + (1.0 - _DECISIVENESS_FLOOR) * (materiality / _DECISIVE_MARGIN)
        )

    horizon = max(0.5, 1.0 - 0.02 * max(0.0, horizon_hours - 12))
    data = 1.0 if using_actual_carbon else 0.85
    tariff = 0.8 if tariff_is_manual else 1.0

    value = decisiveness * horizon * data * tariff
    value = max(0.0, min(1.0, value))

    factors = {
        "there is little difference between the available times": decisiveness,
        "the forecast reaches far into the future": horizon,
        "carbon figures are forecast, not yet measured": data,
        "the tariff was entered manually": tariff,
    }
    weakest_reason = min(factors, key=factors.get)
    caveat = (
        "High-confidence recommendation."
        if _band(value) == "High"
        else f"Treat as indicative: {weakest_reason}."
    )
    return Confidence(value=round(value, 3), band=_band(value), caveat=caveat)
