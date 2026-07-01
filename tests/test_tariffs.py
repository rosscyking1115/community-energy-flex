from __future__ import annotations

from community_energy_flex.data_sources.tariffs import (
    Band,
    Economy7Tariff,
    FlatTariff,
    MultiBandTariff,
    multiband_from_half_hour_prices,
    price_curve,
)


def test_flat_tariff_is_constant():
    t = FlatTariff(unit_rate_p=28.0)
    assert t.unit_rate_p_per_kwh(0) == 28.0
    assert t.unit_rate_p_per_kwh(47) == 28.0


def test_economy7_night_and_day_bands():
    t = Economy7Tariff(day_rate_p=32.0, night_rate_p=14.0, night_start=1, night_end=15)
    assert t.unit_rate_p_per_kwh(0) == 32.0  # 00:00 still day (before 00:30)
    assert t.unit_rate_p_per_kwh(5) == 14.0  # night
    assert t.unit_rate_p_per_kwh(14) == 14.0  # last night slot
    assert t.unit_rate_p_per_kwh(15) == 32.0  # back to day at 07:30


def test_economy7_wraps_past_midnight():
    t = Economy7Tariff(day_rate_p=30.0, night_rate_p=10.0, night_start=46, night_end=2)
    assert t.unit_rate_p_per_kwh(47) == 10.0
    assert t.unit_rate_p_per_kwh(1) == 10.0
    assert t.unit_rate_p_per_kwh(3) == 30.0


def test_multiband_falls_back_to_default():
    t = MultiBandTariff(bands=(Band(10, 20, 8.0),), default_rate_p=25.0)
    assert t.unit_rate_p_per_kwh(15) == 8.0
    assert t.unit_rate_p_per_kwh(5) == 25.0


def test_multiband_from_half_hour_prices_roundtrips():
    prices = [float(i) for i in range(48)]
    t = multiband_from_half_hour_prices(prices)
    assert price_curve(t) == prices
    assert t.is_manual is False
