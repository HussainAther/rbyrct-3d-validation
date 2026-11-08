"""06A2 development checks; no held-out validation fixtures."""
import csv
import json
import numpy as np
import pytest
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_04 import select_order
from experiment_05b_gate import AcquiredOnly
from experiment_06a import acquire_guarded
from experiment_06a2 import run_case, run_development, ray_digest, POLICIES


def fixture():
    n, angles, budget, seed = 4, 2, 48, 1901
    A = system_matrix(n, angles, TILTS).tocsr()
    warm = voxel_coverage_order(A, n, angles, len(TILTS), budget, seed, 8)
    x = .1 + np.linspace(0, .7, n**3)
    observed = np.asarray(A @ x).ravel()
    return A, observed, x, warm, n, angles, budget, seed


def test_unconstrained_06a_matches_frozen_gradient():
    A, obs, x, warm, n, angles, budget, seed = fixture()
    oracle1 = AcquiredOnly(obs); oracle1.commit(warm[:12])
    oracle2 = AcquiredOnly(obs); oracle2.commit(warm[:12])
    frozen, _, _ = select_order(A, oracle1, n, angles, warm, budget, seed,
        policy='gradient', warm_rays=12, batch=6, candidate_pool=8,
        provisional_epochs=2, relaxation=.25)
    loose, _, _ = acquire_guarded(A, oracle2, n, angles, warm, budget, seed,
        eta=float('inf'), warm_rays=12, batch=6, candidate_pool=8,
        provisional_epochs=2, relaxation=.25)
    assert np.array_equal(frozen, loose)


def test_all_policies_matched_and_acquired_only():
    A, obs, truth, warm, n, angles, budget, seed = fixture()
    rows, audits, orders = run_case(A, obs, truth, warm, seed=seed,
        n=n, angles=angles, budget=budget, warm_rays=12, batch=6,
        candidate_pool=8, provisional_epochs=2, final_epochs=4)
    assert [r['policy'] for r in rows] == list(POLICIES)
    assert len(audits) == 12
    assert all(r['acquired_only_verified'] == 1 for r in rows)
    assert all(r['unique_rays'] == budget for r in rows)
    assert all(np.isfinite(r['rmse']) for r in rows)
    assert all(np.array_equal(o[:12], warm[:12]) for o in orders.values())
    assert all(0 <= r['shared_with_coverage'] <= budget for r in rows)
    assert rows[0]['gain_vs_coverage'] == 0.
    assert all(1 <= a['mean_eligible'] <= 8 for a in audits)


def test_deterministic_orders_and_fingerprints():
    A, obs, truth, warm, n, angles, budget, seed = fixture()
    kwargs=dict(seed=seed,n=n,angles=angles,budget=budget,warm_rays=12,
                batch=6,candidate_pool=8,provisional_epochs=2,final_epochs=4)
    a, _, orders_a = run_case(A, obs, truth, warm, **kwargs)
    b, _, orders_b = run_case(A, obs, truth, warm, **kwargs)
    for p in POLICIES:
        assert np.array_equal(orders_a[p], orders_b[p])
        assert ray_digest(orders_a[p]) == ray_digest(orders_b[p])


def test_tiny_end_to_end_and_no_overwrite(tmp_path):
    dest=tmp_path/'run'
    rows, summary, audits = run_development(dest,size=4,angles=2,factor=2,
        families=('branches',),representations=('replicated',),seeds=(1901,),
        budget=48,warm_rays=12,batch=6,candidate_pool=8,
        provisional_epochs=2,final_epochs=4)
    assert len(rows)==4 and len(summary)==4 and len(audits)==12
    with (dest/'development_cases.csv').open(newline='') as f:
        assert len(list(csv.DictReader(f)))==4
    assert json.loads((dest/'protocol.json').read_text())['no_heldout_validation']
    with pytest.raises(ValueError,match='overwrite'):
        run_development(dest,size=4,angles=2,factor=2,families=('branches',),
            representations=('replicated',),seeds=(1901,),budget=48,
            warm_rays=12,batch=6,candidate_pool=8,provisional_epochs=2,final_epochs=4)


def test_rejects_non_development_families(tmp_path):
    with pytest.raises(ValueError,match='allowlist'):
        run_development(tmp_path/'bad',families=('inclusions',))
