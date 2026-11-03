"""Basic tests for RBYRCT-05A coarse-projector benchmarking."""
import unittest

from experiment_05a import benchmark_coarse


class TestExperiment05A(unittest.TestCase):

    def test_small_coarse_projector(self):
        result = benchmark_coarse(
            size=4,
            angles=2,
            tilts=[0.0],
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["matrix_shape"], [32, 64])
        self.assertGreater(result["nonzeros"], 0)
        self.assertGreater(result["csr_storage_mib"], 0)
        self.assertGreaterEqual(
            result["projection_min"], 0
        )


if __name__ == "__main__":
    unittest.main()


def test_small_fine_projector():
    from experiment_05a import benchmark_fine

    result = benchmark_fine(
        size=4,
        angles=2,
        tilts=[0.0],
        factor=2,
    )

    assert result["passed"]
    assert result["matrix_shape"] == [32, 512]
    assert result["nonzeros"] > 0
    assert result["csr_storage_mib"] > 0


def test_uniform_coarse_fine_agreement():
    import numpy as np
    from experiment_04b import system_matrix
    from experiment_04m import high_resolution_matrix

    n = 4
    angles = 2
    tilts = [0.0]
    factor = 2

    coarse = system_matrix(n, angles, tilts)
    fine = high_resolution_matrix(
        n, angles, tilts, factor=factor, offset=0.0
    )

    coarse_y = coarse @ np.ones(n**3)
    fine_y = fine @ np.ones((n * factor)**3)

    assert np.allclose(
        coarse_y, fine_y, rtol=1e-10, atol=1e-10
    )
