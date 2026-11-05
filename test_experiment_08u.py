"""Tests for 08U full-covariance online A-optimal ray ordering."""
import numpy as np
import pytest
from scipy import sparse
from experiment_08u import (append_cholesky, score_full_from_cholesky,
    select_full, order_sha256, object_summary, POLICIES, CHECKPOINTS, MODELS)


def toy():
    return sparse.csr_matrix(np.array([[1.,0.,1.,0.],[0.,1.,1.,0.],[1.,1.,0.,0.],
        [0.,1.,0.,1.],[1.,0.,0.,1.],[1.,1.,1.,1.],[0.,0.,1.,1.],[2.,0.,1.,0.]],dtype=float))


def factor_for(A, selected, tau=1., sigma=1.):
    H=A[selected]
    return np.linalg.cholesky(sigma*np.eye(len(selected))+tau*(H@H.T).toarray())


def test_incremental_cholesky_matches_full_factor():
    A=toy(); selected=[]; L=np.zeros((0,0))
    for ray in (0,2,4,7):
        L=append_cholesky(A,selected,L,ray)
        selected.append(ray)
        np.testing.assert_allclose(L@L.T, np.eye(len(selected))+(A[selected]@A[selected].T).toarray(),rtol=1e-12,atol=1e-12)


def test_exact_scores_match_direct_posterior():
    A=toy();selected=[0,2,4]; candidates=[1,3,5,6,7]
    L=factor_for(A,selected)
    score=score_full_from_cholesky(A,selected,L,candidates)
    H=A[selected].toarray()
    C=np.linalg.inv(np.eye(A.shape[1])+H.T@H)
    want=np.array([float(a@C@C@a/(1+a@C@a)) for a in A[candidates].toarray()])
    np.testing.assert_allclose(score,want,rtol=1e-11,atol=1e-12)


def test_scores_arbitrary_variance():
    A=toy(); selected=[1,2]; cand=[3,4,7];tau=2.5;sig=.7
    H=A[selected].toarray();L=factor_for(A,selected,tau,sig)
    got=score_full_from_cholesky(A,selected,L,cand,prior_variance=tau,observation_variance=sig)
    C=np.linalg.inv(np.eye(A.shape[1])/tau+H.T@H/sig)
    want=[a@C@C@a/(sig+a@C@a) for a in A[cand].toarray()]
    np.testing.assert_allclose(got,want,rtol=1e-11,atol=1e-12)


def test_full_deterministic_and_unique():
    A=toy();warm=np.array([0,1]);o1,t1=select_full(A,None,warm,7,41,warm_rays=2,batch=2,candidate_pool=3)
    o2,t2=select_full(A,None,warm,7,41,warm_rays=2,batch=2,candidate_pool=3)
    assert np.array_equal(o1,o2) and len(set(o1))==7
    assert list(o1[:2])==[0,1] and t1>=0 and t2>=0


def test_no_detector_reads():
    class Recorder:
        def __init__(self):self.commits=[]
        def __getitem__(self, key):raise AssertionError('measurement leaked into selector')
        def commit(self, ids):self.commits.extend(ids)
    A=toy();o=Recorder()
    rays,_=select_full(A,o,np.array([0,1]),6,1,warm_rays=2,batch=2,candidate_pool=3)
    assert o.commits==list(rays[2:])


def test_reject_duplicate_warm_and_budget():
    A=toy()
    with pytest.raises(ValueError):select_full(A,None,[0,0],6,1,warm_rays=2)
    with pytest.raises(ValueError):select_full(A,None,[0,1],9,1,warm_rays=2)


def test_reject_duplicate_cholesky_update():
    A=toy();L=append_cholesky(A,[],np.zeros((0,0)),0)
    with pytest.raises(ValueError):append_cholesky(A,[0],L,0)


def test_reject_bad_candidates():
    A=toy();L=factor_for(A,[0])
    with pytest.raises(ValueError):score_full_from_cholesky(A,[0],L,[1,1])
    with pytest.raises(ValueError):score_full_from_cholesky(A,[0],np.zeros((0,0)),[1])


def test_sha_order_sensitive():
    assert order_sha256([0,1,2])!=order_sha256([0,2,1])


def test_object_aggregation_does_not_count_models_as_objects():
    rows=[]
    for k in CHECKPOINTS:
        for p in POLICIES:
            for model in MODELS:
                rows.append(dict(object_id='one',acquired=k,policy=p,model=model,
                    gain_vs_coverage=.1,defect_gain_vs_coverage=.2,global_rmse=.3,defect_region_rmse=.4))
    agg=object_summary(rows)
    assert len(agg)==len(POLICIES)*len(CHECKPOINTS)
    assert all(r['n_models']==len(MODELS) for r in agg)


def test_no_unexpected_success_claim():
    import experiment_08u as ex
    assert ex.OBJECT_SEEDS!=tuple(range(8))
    assert ex.SIZE==12 and ex.POLICIES==('coverage','information_diag','information_full')


def test_real_12cube_geometry_exact_selector_short_budget():
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    from experiment_04h import voxel_coverage_order
    A=system_matrix(12,4,TILTS).tocsr()
    warm=voxel_coverage_order(A,12,4,len(TILTS),48,880423,16)
    order,_=select_full(A,None,warm,48,880423,warm_rays=24,batch=16,candidate_pool=16)
    assert len(order)==48 and len(set(order.tolist()))==48
    np.testing.assert_array_equal(order[:24],warm[:24])
