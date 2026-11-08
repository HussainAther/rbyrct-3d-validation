"""Focused 05B-06 acquired-only ranking audit regression tests."""
import numpy as np
import pytest
from experiment_04b import system_matrix
from experiment_05b_06 import acquired_only_scores, analyze_prefix, offline_one_ray_value


def fixture():
    n,angles=4,2
    A=system_matrix(n,angles,[-20.,0.,20.]).tocsr()
    truth=np.full(n**3,.3)
    truth[3]=.8
    observed=np.asarray(A@truth).ravel()
    prefix=np.arange(12,dtype=np.int64)
    candidates=np.arange(12,20,dtype=np.int64)
    return A,observed,truth,prefix,candidates,n,angles


def test_scores_never_access_future_candidate_observations():
    A,obs,_,prefix,candidates,n,angles=fixture()
    class Guard:
        def __getitem__(self,idx):
            if not np.isin(np.asarray(idx),prefix).all():
                raise AssertionError('future measurement accessed')
            return obs[idx]
    result=acquired_only_scores(A,Guard(),prefix,candidates,n,angles,2,.25,3.)
    assert set(result)=={'coverage','gradient','capped_gradient','projection_disagreement'}
    assert all(np.isfinite(v).all() and len(v)==len(candidates) for v in result.values())


def test_offline_candidate_value_is_finite():
    A,obs,truth,prefix,candidates,_,_=fixture()
    heldout=np.setdiff1d(np.arange(A.shape[0]),np.r_[prefix,candidates])
    v=offline_one_ray_value(A,obs,truth,prefix,int(candidates[0]),3,.25,heldout)
    assert all(np.isfinite(x) for x in v.values())
    assert v['rmse_reduction']==pytest.approx(v['baseline_rmse']-v['augmented_rmse'])


def test_prefix_summary_and_best_regret():
    A,obs,truth,prefix,candidates,n,angles=fixture()
    rows,summaries=analyze_prefix(A,obs,truth,prefix,candidates,n,angles,
                                  provisional_epochs=2,final_epochs=3,relaxation=.25,feature_cap=3.)
    assert len(rows)==8 and len(summaries)==4
    assert all(x['one_step_regret']>=0 for x in summaries)
    assert all(x['chosen_ray'] in candidates for x in summaries)


def test_cannot_evaluate_acquired_candidate():
    A,obs,truth,prefix,candidates,_,_=fixture()
    with pytest.raises(ValueError):
        offline_one_ray_value(A,obs,truth,prefix,int(prefix[0]),2,.25,candidates)
