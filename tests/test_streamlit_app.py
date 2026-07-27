"""Headless smoke test of the Streamlit app via AppTest. Skips where Streamlit
isn't installed (it's the optional 'app' extra)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

import pandas as pd  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=30).run()


def test_app_starts_without_error():
    at = _app()
    assert not at.exception
    labels = [s.label for s in at.sidebar.selectbox]
    assert "Demo role" in labels  # auth account picker rendered


def test_household_can_run_the_optimiser():
    at = _app()
    at.button[0].click().run()  # "Find the best times"
    assert not at.exception
    assert len(at.metric) == 2  # cost + carbon saving metrics


def test_plan_survives_a_rerun():
    """A download click reruns the script. The plan must not vanish with it."""
    at = _app()
    at.button[0].click().run()
    assert len(at.metric) == 2
    at.run()  # any rerun: download button, sidebar change, widget interaction
    assert not at.exception
    assert len(at.metric) == 2


def test_changed_inputs_mark_the_plan_stale_without_hiding_it():
    at = _app()
    at.button[0].click().run()
    assert len(at.warning) == 0
    at.sidebar.selectbox[1].set_value("Economy 7").run()  # tariff differs from the plan
    assert len(at.metric) == 2  # still shown
    assert any("set-up has changed" in w.value for w in at.warning)
    at.button[0].click().run()  # re-planning clears the notice
    assert len(at.warning) == 0


def test_a_plan_does_not_outlive_the_role_that_could_produce_it():
    at = _app()
    at.button[0].click().run()
    assert len(at.metric) == 2
    at.sidebar.selectbox[0].set_value("public").run()
    assert len(at.metric) == 0


def test_duplicate_appliance_names_are_rejected():
    at = _app()
    frame = at.session_state["task_frame"]
    duplicated = pd.concat([frame.head(1), frame.head(1)], ignore_index=True)
    at.session_state["task_frame"] = duplicated
    at.run()
    at.button[0].click().run()
    assert not at.exception
    assert any("must be unique" in e.value for e in at.error)
    assert len(at.metric) == 0


@pytest.mark.parametrize("role", ["public", "community_manager"])
def test_roles_without_permission_are_blocked(role):
    at = _app()
    at.sidebar.selectbox[0].set_value(role).run()
    at.button[0].click().run()
    assert not at.exception
    assert len(at.metric) == 0  # optimiser did not run
    assert len(at.info) > 0  # a "you can't run this" message is shown
