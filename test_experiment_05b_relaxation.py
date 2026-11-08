"""Regression tests for MART relaxation propagation."""

from unittest.mock import patch

import numpy as np

from experiment_04b import system_matrix
from experiment_05b_mart import mart_reconstruct
from experiment_05b_adaptive import adaptive_order
from experiment_05b_diagnostics import acquired_only_reliability
from experiment_05b_gate import online_order


def test_mart_relaxation_reaches_all_shared_components():
    n = 4
    angles = 2
    A = system_matrix(n, angles, [-20.0, 0.0, 20.0])

    truth = np.full(n**3, 0.5)
    observed = A @ truth

    warm = np.arange(12, dtype=np.int64)
    relaxation = 0.25
    seen = []

    def spy(A_sub, b_sub, epochs, *args, **kwargs):
        seen.append(kwargs.get("relaxation"))
        return mart_reconstruct(
            A_sub, b_sub, epochs, *args, **kwargs
        )

    with patch(
        "experiment_05b_adaptive.mart_reconstruct",
        side_effect=spy,
    ):
        adaptive_order(
            A, observed, n, angles, warm,
            budget=16, seed=271828,
            warm_rays=12, batch=4,
            provisional_epochs=2,
            candidate_pool=8,
            mart_relaxation=relaxation,
        )

    assert seen and all(v == relaxation for v in seen)

    seen.clear()

    with patch(
        "experiment_05b_diagnostics.mart_reconstruct",
        side_effect=spy,
    ):
        acquired_only_reliability(
            A, observed, warm, n,
            epochs=2,
            holdout_fraction=0.25,
            mart_relaxation=relaxation,
        )

    assert len(seen) == 3
    assert all(v == relaxation for v in seen)

    seen.clear()

    with (
        patch(
            "experiment_05b_gate.mart_reconstruct",
            side_effect=spy,
        ),
        patch(
            "experiment_05b_diagnostics.mart_reconstruct",
            side_effect=spy,
        ),
    ):
        online_order(
            A, observed, n, angles, warm,
            budget=16, seed=271828,
            warm_rays=12, batch=4,
            provisional_epochs=2,
            diagnostic_epochs=2,
            candidate_pool=8,
            mart_relaxation=relaxation,
        )

    assert len(seen) >= 4
    assert all(v == relaxation for v in seen)
