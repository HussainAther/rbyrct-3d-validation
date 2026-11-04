"""06A unit tests; no held-out or confirmatory data accessed."""
import numpy as np
import pytest
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_adaptive import score_candidates
from experiment_05b_gate import AcquiredOnly
from experiment_06a import choose_guarded, acquire_guarded, projected_imbalance, run_development_smoke


def fixture():
    n=4;angles=2
    A=system_matrix(n,angles,TILTS).tocsr()
    warm=voxel_coverage_order(A,n,angles,len(TILTS),48,1901,8)
    counts=np.asarray(A[warm[:12]].sum(axis=0)).ravel()
    views=np.bincount(warm[:12]//(n*n),minlength=angles*len(TILTS))
    pool=np.array([i for i in range(A.shape[0]) if i not in set(warm[:12])][:8])
    feat=1.+np.linspace(0,1,n**3)
    return A,n,angles,warm,counts,views,pool,feat


def test_reference_is_feasible_under_strict_guard():
    A,n,angles,warm,counts,views,pool,feat=fixture()
    ray,a=choose_guarded(A,pool,counts,views,n,feat,eta=0.)
    assert a['chosen_imbalance'] <= a['reference_imbalance']+1e-12
    assert 1<=a['admissible_count']<=len(pool)


def test_loose_guard_matches_frozen_gradient_score():
    A,n,angles,warm,counts,views,pool,feat=fixture()
    ray,a=choose_guarded(A,pool,counts,views,n,feat,eta=float('inf'))
    score=score_candidates(A,pool,counts,views,n,feat,feedback_strength=1.)
    winners=pool[np.isclose(score,score.max(),rtol=1e-13,atol=1e-14)]
    assert ray==min(winners)
    assert a['admissible_count']==len(pool)


def test_invalid_guards_and_counters():
    A,n,angles,warm,counts,views,pool,feat=fixture()
    with pytest.raises(ValueError):choose_guarded(A,pool,counts,views,n,feat,eta=-1)
    with pytest.raises(ValueError):choose_guarded(A,pool,counts,views,n,feat,eta=np.nan)
    with pytest.raises(ValueError):projected_imbalance(A,pool,np.zeros(7))


def test_acquired_only_and_reproducible():
    A,n,angles,warm,counts,views,pool,feat=fixture()
    obs=np.asarray(A@(.1+np.linspace(0,.8,n**3))).ravel()
    runs=[]
    for _ in range(2):
        guard=AcquiredOnly(obs);guard.commit(warm[:12])
        order,trace,_=acquire_guarded(A,guard,n,angles,warm,48,1901,
            warm_rays=12,batch=6,candidate_pool=8,provisional_epochs=2,eta=.05)
        assert len(np.unique(order))==48
        assert len(trace)==6
        assert np.array_equal(order[:12],warm[:12])
        runs.append(order)
    assert np.array_equal(*runs)


def test_smoke_writes_and_refuses_overwrite(tmp_path):
    out=tmp_path/'dev'
    rows=run_development_smoke(out)
    assert len(rows)==3
    assert (out/'protocol.json').exists()
    assert (out/'batch_audit.csv').exists()
    with pytest.raises(ValueError,match='overwrite'):
        run_development_smoke(out)
