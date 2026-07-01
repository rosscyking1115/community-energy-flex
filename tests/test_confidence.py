from __future__ import annotations

from community_energy_flex.optimisation.confidence import compute_confidence


def _c(scores, **kw):
    defaults = dict(horizon_hours=1.0, using_actual_carbon=True, tariff_is_manual=False)
    defaults.update(kw)
    return compute_confidence(scores, **defaults)


def test_decisive_winner_is_high_confidence():
    conf = _c([0.0, 0.3, 0.6])
    assert conf.band == "High"
    assert conf.caveat == "High-confidence recommendation."


def test_flat_landscape_lowers_confidence():
    # When the best option barely beats the typical option, the choice is
    # low-stakes and confidence should reflect that.
    decisive = _c([0.0, 0.5, 0.5])
    flat = _c([0.0, 0.02, 0.02])
    assert flat.value < decisive.value


def test_manual_tariff_and_forecast_reduce_confidence():
    trusted = _c([0.0, 0.3], using_actual_carbon=True, tariff_is_manual=False)
    shaky = _c([0.0, 0.3], using_actual_carbon=False, tariff_is_manual=True)
    assert shaky.value < trusted.value


def test_caveat_names_the_weakest_factor():
    # Decisive choice + measured carbon, but a long horizon and a manual tariff
    # pull it out of the "High" band. The manual tariff (0.8) is the weakest
    # single factor, so it should surface as the caveat.
    conf = _c(
        [0.0, 0.4, 0.6],
        horizon_hours=17,  # horizon factor ~0.9
        tariff_is_manual=True,  # tariff factor 0.8 (weakest)
        using_actual_carbon=True,
    )
    assert conf.band != "High"
    assert "tariff" in conf.caveat.lower()


def test_single_option_is_neither_strong_nor_weak():
    conf = compute_confidence(
        [0.0], horizon_hours=1.0, using_actual_carbon=True,
        tariff_is_manual=False, single_option=True,
    )
    assert 0.5 <= conf.value <= 0.75
