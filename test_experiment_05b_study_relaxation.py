"""Verify that both MART study CLIs forward the requested relaxation.

Keep test geometry intentionally tiny and synthetic; no scientific claim.
"""
from unittest.mock import patch

import pytest

import experiment_05b_04p as study_p
import experiment_05b_04qb as study_qb


@pytest.mark.parametrize("study", [study_p, study_qb])
def test_study_cli_forwards_mart_relaxation(study, tmp_path):
    observed = {"adaptive": [], "gate": [], "final": []}
    original_adaptive = study.adaptive_order
    original_gate = study.online_order
    original_mart = study.mart_reconstruct

    def capture_adaptive(*args, **kwargs):
        observed["adaptive"].append(kwargs.get("mart_relaxation"))
        return original_adaptive(*args, **kwargs)

    def capture_gate(*args, **kwargs):
        observed["gate"].append(kwargs.get("mart_relaxation"))
        return original_gate(*args, **kwargs)

    def capture_mart(*args, **kwargs):
        observed["final"].append(kwargs.get("relaxation"))
        return original_mart(*args, **kwargs)

    args = [
        "--size", "4", "--angles", "2", "--factor", "2",
        "--phantoms", "branches", "--object-types", "replicated",
        "--offsets", "0", "--budgets", "16", "--seeds", "271828",
        "--noise-fractions", "0", "--warm-rays", "12", "--batch", "4",
        "--provisional-epochs", "2", "--diagnostic-epochs", "2",
        "--mart-epochs", "2", "--candidate-pool", "8",
        "--diagnostic-every", "4", "--mart-relaxation", "0.25",
        "--output-dir", str(tmp_path / study.__name__),
    ]
    with (patch.object(study, "adaptive_order", side_effect=capture_adaptive),
          patch.object(study, "online_order", side_effect=capture_gate),
          patch.object(study, "mart_reconstruct", side_effect=capture_mart)):
        study.main(args)

    assert observed["adaptive"] == [0.25, 0.25]
    assert observed["gate"] == [0.25]
    assert observed["final"] == [0.25] * 5
