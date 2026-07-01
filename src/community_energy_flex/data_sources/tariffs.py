"""Electricity tariff models.

Every tariff exposes ``unit_rate_p_per_kwh(slot_index)`` and a per-day
``standing_charge_p``. The optimiser only ever uses the *unit rate*: the
standing charge is a fixed daily cost that does not change when a task is
shifted, so including it in savings would distort the numbers (see
docs/METHODOLOGY.md). ``is_manual`` flags tariffs typed in by hand, which the
confidence model treats as less certain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from community_energy_flex.domain.models import SLOTS_PER_DAY


@runtime_checkable
class Tariff(Protocol):
    name: str
    standing_charge_p: float
    is_manual: bool

    def unit_rate_p_per_kwh(self, slot_index: int) -> float: ...


def price_curve(tariff: Tariff, num_slots: int = SLOTS_PER_DAY) -> list[float]:
    """Expand a tariff into a per-slot unit-rate array."""
    return [tariff.unit_rate_p_per_kwh(i) for i in range(num_slots)]


@dataclass(frozen=True)
class FlatTariff:
    """A single unit rate all day (e.g. a standard variable tariff)."""

    unit_rate_p: float
    standing_charge_p: float = 0.0
    name: str = "Flat rate"
    is_manual: bool = True

    def unit_rate_p_per_kwh(self, slot_index: int) -> float:
        return self.unit_rate_p


@dataclass(frozen=True)
class Economy7Tariff:
    """A two-rate day/night tariff. ``night_start``/``night_end`` are slot
    indices; the night band wraps past midnight when start > end."""

    day_rate_p: float
    night_rate_p: float
    night_start: int = 1  # 00:30
    night_end: int = 15  # 07:30
    standing_charge_p: float = 0.0
    name: str = "Economy 7"
    is_manual: bool = True

    def _is_night(self, slot_index: int) -> bool:
        s = slot_index % SLOTS_PER_DAY
        if self.night_start <= self.night_end:
            return self.night_start <= s < self.night_end
        return s >= self.night_start or s < self.night_end

    def unit_rate_p_per_kwh(self, slot_index: int) -> float:
        return self.night_rate_p if self._is_night(slot_index) else self.day_rate_p


@dataclass(frozen=True)
class Band:
    start: int  # inclusive slot index
    end: int  # exclusive slot index
    rate_p: float


@dataclass(frozen=True)
class MultiBandTariff:
    """A generic time-of-use tariff: a list of ``Band`` windows plus a default
    rate for any slot not covered by a band. Suits Agile-style tariffs."""

    bands: tuple[Band, ...]
    default_rate_p: float
    standing_charge_p: float = 0.0
    name: str = "Time-of-use"
    is_manual: bool = True

    def unit_rate_p_per_kwh(self, slot_index: int) -> float:
        s = slot_index % SLOTS_PER_DAY
        for band in self.bands:
            if band.start <= s < band.end:
                return band.rate_p
        return self.default_rate_p


def multiband_from_half_hour_prices(
    prices_p: list[float],
    standing_charge_p: float = 0.0,
    name: str = "Half-hourly",
    is_manual: bool = False,
) -> MultiBandTariff:
    """Build a tariff from a 48-length list of half-hourly prices (e.g. an
    Agile export). One band per slot; the mean is the default rate."""
    bands = tuple(Band(i, i + 1, p) for i, p in enumerate(prices_p))
    default = sum(prices_p) / len(prices_p) if prices_p else 0.0
    return MultiBandTariff(
        bands=bands,
        default_rate_p=default,
        standing_charge_p=standing_charge_p,
        name=name,
        is_manual=is_manual,
    )
