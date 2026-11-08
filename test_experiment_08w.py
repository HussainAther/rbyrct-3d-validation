import numpy as np
import pytest
from scipy import sparse

from experiment_08w import (ALPHA, blended_scores, normalized, detector_entropy,
    select_full_diverse, object_aggregate, POLICIES, CHECKPOINTS, MODELS)
from experiment_08u import select_full


def toy():
    rng=np.random.default_rng(4)
    return sparse.csr_matrix(rng.uniform(.01,1,(64,16)))


def test_normalize_extrema():
    assert np.allclose(normalized([2,3,4]),[0,.5,1])


def test_normalize_constant():
    assert np.array_equal(normalized([1,1,1]),[0,0,0])


def test_blend_zero_is_original_scores():
    scores=np.array([.01,.04,.08])
    assert np.array_equal(blended_scores(scores,[4,1,0],[0,1,2],0),scores)


def test_diversity_reward_favors_less_visited_bin():
    scores=[1.,1.]
    result=blended_scores(scores,[5,0],[0,1],ALPHA)
    assert result[1]>result[0]


def test_alpha_invalid():
    with pytest.raises(ValueError):blended_scores([1],[0],[0],-1)
    with pytest.raises(ValueError):blended_scores([1],[0],[0],2)


def test_invalid_detector_index():
    with pytest.raises(ValueError):blended_scores([1],[0],[1],.25)


def test_deterministic_unique_and_alpha_zero_matches_full():
    A=toy(); warm=np.arange(6)
    a,_=select_full_diverse(A,None,warm,28,31,size=4,warm_rays=6,batch=4,candidate_pool=5)
    b,_=select_full_diverse(A,None,warm,28,31,size=4,warm_rays=6,batch=4,candidate_pool=5)
    assert np.array_equal(a,b) and len(set(a))==28
    old,_=select_full(A,None,warm,28,31,warm_rays=6,batch=4,candidate_pool=5)
    zero,_=select_full_diverse(A,None,warm,28,31,size=4,alpha=0,warm_rays=6,batch=4,candidate_pool=5)
    assert np.array_equal(old,zero)


def test_no_observation_reads_and_batch_commits():
    class Sink:
        def __init__(self): self.rays=[]
        def __getitem__(self,k): raise AssertionError('detector leak')
        def commit(self,ids): self.rays.extend(ids)
    A=toy();s=Sink()
    arr,_=select_full_diverse(A,s,np.arange(6),22,42,size=4,warm_rays=6,batch=5,candidate_pool=4)
    assert s.rays==list(arr[6:])


def test_reject_duplicate_warm():
    with pytest.raises(ValueError):
        select_full_diverse(toy(),None,[0,0,1],10,4,size=4,warm_rays=3,batch=2,candidate_pool=4)


def test_detector_entropy_bounds():
    assert 0<=detector_entropy([0,1,2,3],size=4)<=1
    assert detector_entropy([0,16,32,48],size=4)<detector_entropy([0,1,2,3],size=4)


def test_object_aggregation_keeps_models_paired():
    rows=[]
    for oid in ('a','b'):
        for k in CHECKPOINTS:
            for policy in POLICIES:
                for model in MODELS:
                    rows.append(dict(object_id=oid,acquired=k,policy=policy,model=model,
                        gain_vs_coverage=.1 if oid=='a' else -.1,
                        defect_gain_vs_coverage=.2,global_rmse=.3,defect_region_rmse=.4))
    summary=object_aggregate(rows)
    assert len(summary)==2*len(CHECKPOINTS)*len(POLICIES)
    assert all(row['n_models']==2 for row in summary)


def test_geometry_level_selector_smoke():
    try:
        from experiment_08w import geometry, SIZE, BUDGET, WARM
        A=geometry()
    except ImportError:
        pytest.skip('older RBYRCT modules unavailable in this environment')
    warm=np.arange(24)
    result,_=select_full_diverse(A,None,warm,40,8904,size=12,warm_rays=WARM,batch=8,candidate_pool=5)
    assert len(set(result))==40
