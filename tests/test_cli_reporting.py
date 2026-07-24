from __future__ import annotations

from community_energy_flex.__main__ import main


def test_demo_cli_passes_explicit_preferred_evidence_to_the_reporter(capsys):
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "Illustrative sample-input planning result" in output
    assert "Illustrative cost difference" in output
    assert "Not reportable" not in output
