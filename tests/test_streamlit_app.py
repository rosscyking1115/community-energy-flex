"""Headless smoke test of the Streamlit app via AppTest. Skips where Streamlit
isn't installed (it's the optional 'app' extra)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

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


@pytest.mark.parametrize("role", ["public", "community_manager"])
def test_roles_without_permission_are_blocked(role):
    at = _app()
    at.sidebar.selectbox[0].set_value(role).run()
    at.button[0].click().run()
    assert not at.exception
    assert len(at.metric) == 0  # optimiser did not run
    assert len(at.info) > 0  # a "you can't run this" message is shown
