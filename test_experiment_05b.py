"""Regression tests for MART restoration; never edit historical 04 series."""
from pathlib import Path
import json
import numpy as np
import pytest
from scipy import sparse
from experiment_04b import mart as reference_mart
from experiment_05b_mart import mart_reconstruct
from experiment_05b_adaptive import adaptive_order
from experiment_05b_gate import AcquiredOnly, online_order
from experiment_05b_benchmark import run


def test_mart_matches_reference_04b():
    A = sparse.csr_matrix([[1., 0., .3], [.1, 1., 0], [0., .5, 1.]])
    b = np.array([.6, .8, .5])
    truth = np.full(3, .3)
    ref, _ = reference_mart(A, b, truth, epochs=4, relaxation=.15, checkpoint_interval=4)
    new = mart_reconstruct(A, b, epochs=4, relaxation=.15)
    np.testing.assert_allclose(new, ref, rtol=1e-13, atol=1e-13)


def test_mart_nonnegative_and_zero_ray():
    A = sparse.csr_matrix([[1., 1.], [0., 1.]])
    x = mart_reconstruct(A, np.array([0., 0.]), epochs=5)
    assert np.all(np.isfinite(x)) and np.all(x > 0)
    assert np.all(x < .3)


@pytest.mark.parametrize('bad', [[-1.], [float('nan')], [float('inf')]])
def test_mart_rejects_invalid_measurements(bad):
    with pytest.raises(ValueError):
        mart_reconstruct(sparse.eye(1, format='csr'), np.array(bad), epochs=1)


def test_mart_order_validation():
    A = sparse.eye(2, format='csr')
    with pytest.raises(ValueError):
        mart_reconstruct(A, np.ones(2), epochs=1, ray_order=np.array([0, 0]))


def test_acquired_only_rejects_future_observation():
    oracle = AcquiredOnly(np.arange(12., dtype=float))
    oracle.commit([2, 3])
    np.testing.assert_array_equal(oracle[np.array([2,3])], [2.,3.])
    with pytest.raises(AssertionError):
        _ = oracle[np.array([1])]


def test_mart_selector_feedback_independent_of_unacquired_measurements():
    from experiment_04b import system_matrix
    A = system_matrix(4, 2, [-20., 0., 20.]).tocsr()
    warm = np.arange(12, dtype=int)
    obs = np.linspace(.01, 1., A.shape[0])
    changed = obs.copy(); changed[12:] += 1000
    # Both runs see identical 12 warm measurements and choose the next batch before reading it.
    ids1, _, _ = adaptive_order(A, obs, 4, 2, warm, 16, 123,
                                warm_rays=12, batch=4, provisional_epochs=2, candidate_pool=8)
    ids2, _, _ = adaptive_order(A, changed, 4, 2, warm, 16, 123,
                                warm_rays=12, batch=4, provisional_epochs=2, candidate_pool=8)
    np.testing.assert_array_equal(ids1, ids2)


def test_mart_benchmark_small():
    result = run(size=4, angles=2, budget=16, mart_epochs=8, sirt_iterations=10)
    assert result['results']['MART']['passed']
    assert result['results']['SIRT']['passed']


def test_mart_main_studies_cli_smoke(tmp_path):
    """Both manuscript studies must run with MART feedback, gate and final reconstruction."""
    from experiment_05b_04p import main as main_p
    from experiment_05b_04qb import main as main_qb
    args = [
        '--size', '4', '--angles', '2', '--factor', '2',
        '--phantoms', 'branches', '--object-types', 'replicated',
        '--offsets', '0', '--budgets', '16', '--seeds', '271828',
        '--noise-fractions', '0', '--warm-rays', '12', '--batch', '4',
        '--provisional-epochs', '2', '--diagnostic-epochs', '2',
        '--mart-epochs', '2', '--candidate-pool', '8',
        '--diagnostic-every', '4',
    ]
    for suffix, main in [('p',main_p),('qb',main_qb)]:
        target = tmp_path / suffix
        main(args + ['--output-dir', str(target)])
        protocol = json.loads((target/'protocol.json').read_text())
        assert protocol['experiment'].startswith('05B-')
        assert 'multiplicative' in protocol['mart_update']
        if 'reconstructor' in protocol:
            assert 'MART' in protocol['reconstructor']
        import csv
        with (target/'metrics.csv').open(newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 5
        assert {r['policy'] for r in rows} == {
            'adaptive_feedback', 'feedback_off_control', 'geometry_balanced',
            'voxel_coverage_greedy', 'reliability_gate'
        }
        assert all(np.isfinite(float(r['rmse'])) for r in rows)


def test_large_grid_refused_without_opt_in():
    from experiment_05b_resources import validate_grid
    with pytest.raises(ValueError, match='allow-large'):
        validate_grid(24, 2, allow_large=False)
    with pytest.raises(ValueError, match='RAM floor'):
        validate_grid(24, 2, allow_large=True, min_free_ram_gib=1.)
