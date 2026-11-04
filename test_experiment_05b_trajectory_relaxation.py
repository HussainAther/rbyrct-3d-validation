"""Small integration regression for MART trajectory relaxation provenance."""
import json
import sys

import pytest

from experiment_05b_04r import main as trajectory_main
from experiment_05b_04s import main as replay_main


def test_trajectory_relaxation_and_matching_replay(monkeypatch, tmp_path):
    source = tmp_path / "trajectory"
    output = tmp_path / "matched"
    common = [
        "--phantom", "branches", "--size", "4", "--angles", "2",
        "--factor", "2", "--budget", "16", "--warm-rays", "12",
        "--batch", "2", "--candidate-pool", "8",
        "--provisional-epochs", "2", "--mart-epochs", "2",
    ]
    monkeypatch.setattr(sys, "argv", ["experiment_05b_04r.py", *common,
                                    "--mart-relaxation", "0.25",
                                    "--output-dir", str(source)])
    trajectory_main()
    protocol = json.loads((source / "protocol.json").read_text())
    assert protocol["arguments"]["mart_relaxation"] == 0.25

    replay_args = [*common, "--switch-at", "14",
                   "--source-dir", str(source), "--output-dir", str(output)]
    monkeypatch.setattr(sys, "argv", ["experiment_05b_04s.py", *replay_args,
                                    "--mart-relaxation", "0.15"])
    with pytest.raises(SystemExit):
        replay_main()
    assert not output.exists()

    monkeypatch.setattr(sys, "argv", ["experiment_05b_04s.py", *replay_args,
                                    "--mart-relaxation", "0.25"])
    replay_main()
    assert (output / "matched_prefix_comparisons.csv").is_file()
    replay_protocol = json.loads((output / "protocol.json").read_text())
    assert replay_protocol["same_policy_replay_verified"] is True
    assert replay_protocol["arguments"]["mart_relaxation"] == 0.25
