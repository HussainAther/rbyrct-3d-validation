"""Focused tests for 08Z spatial sensitivity policy and paired study bookkeeping."""
import numpy as np
import pytest
from scipy import sparse

from experiment_08z import (
    ALPHA, BUDGET, CHECKPOINTS, MODELS, POLICIES,
    normalized, spatial_novelty, spatial_blend, sensitivity_gini,
    select_full_spatial, object_aggregate,
)
from experiment_08u import select_full


def toy():
    return sparse.csr_matrix(np.random.default_rng(734).uniform(.01, 1, (64, 16)))


def test_normalize():
    assert np.allclose(normalized([2, 3, 4]), [0, .5, 1])


def test_normalize_constant():
    assert np.array_equal(normalized([3, 3]), [0, 0])


def test_spatial_novelty_prefers_unsampled_voxels():
    A=sparse.csr_matrix([[1., 0.], [0., 1.]])
    novelty=spatial_novelty(A,[0,1],np.array([3.,0.]))
    assert novelty[1]>novelty[0]


def test_spatial_novelty_accounts_for_row_weights():
    A=sparse.csr_matrix([[3., 1.], [1., 3.]])
    novelty=spatial_novelty(A,[0,1],np.array([3., 0.]))
    assert novelty[1]>novelty[0]
    assert np.allclose(novelty,[-2.25,-.75])


def test_novelty_rejects_wrong_sensitivity_shape():
    with pytest.raises(ValueError):spatial_novelty(toy(),[0],np.zeros(5))


def test_novelty_rejects_negative_prior_sensitivity():
    with pytest.raises(ValueError):spatial_novelty(sparse.eye(2,format='csr'),[0],[-1,2])


def test_blending_favors_novelty_for_equal_full_scores():
    x=spatial_blend([1,1],[-3,0],ALPHA)
    assert x[1]>x[0]


def test_blending_zero_exactly_preserves_full_score():
    original=np.array([.1,.4,.4])
    assert np.array_equal(spatial_blend(original,[100,1,2],0),original)


def test_blending_rejects_invalid_alpha():
    for bad in [-.01, 1.01, float('nan')]:
        with pytest.raises(ValueError):spatial_blend([1,2],[1,2],bad)


def test_blending_rejects_invalid_shapes():
    with pytest.raises(ValueError):spatial_blend([1,2],[1],.25)


def test_gini_equal_zero_and_concentrated():
    equal=sparse.csr_matrix([[1.,1.,1.,1.]])
    unequal=sparse.csr_matrix([[4.,0.,0.,0.]])
    assert sensitivity_gini(equal,[0])==pytest.approx(0)
    assert sensitivity_gini(unequal,[0])==pytest.approx(.75)


def test_gini_weighted_not_binary_visitation():
    A=sparse.csr_matrix([[4.,1.],[1.,1.]])
    assert sensitivity_gini(A,[0])>sensitivity_gini(A,[1])


def test_selector_deterministic_unique_and_zero_equivalence():
    A=toy()
    warm=np.arange(6)
    kwargs=dict(size=4,warm_rays=6,batch=4,candidate_pool=5)
    result,_=select_full_spatial(A,None,warm,28,31,**kwargs)
    repeat,_=select_full_spatial(A,None,warm,28,31,**kwargs)
    zero,_=select_full_spatial(A,None,warm,28,31,alpha=0,**kwargs)
    original,_=select_full(A,None,warm,28,31,warm_rays=6,batch=4,candidate_pool=5)
    assert np.array_equal(result,repeat)
    assert np.array_equal(zero,original)
    assert np.array_equal(result[:6],warm)
    assert len(np.unique(result))==28


def test_selector_cannot_read_measurements_and_commits_batches():
    class Sink:
        def __init__(self):self.rays=[]
        def __getitem__(self,key):raise AssertionError('measurement leakage')
        def commit(self,rays):self.rays.extend(rays)
    A=toy();sink=Sink()
    order,_=select_full_spatial(A,sink,np.arange(6),22,42,
                                size=4,warm_rays=6,batch=5,candidate_pool=4)
    assert sink.rays==list(order[6:])


def test_selector_rejects_bad_warm():
    with pytest.raises(ValueError):
        select_full_spatial(toy(),None,[0,0,1],10,4,size=4,warm_rays=3,batch=2,candidate_pool=4)


def test_object_aggregation_paired_not_pseudoreplication():
    rows=[]
    for oid in ('a','b'):
        for k in CHECKPOINTS:
            for policy in POLICIES:
                for model in MODELS:
                    rows.append(dict(object_id=oid,acquired=k,policy=policy,model=model,
                                     gain_vs_coverage=.1 if oid=='a' else -.1,
                                     defect_gain_vs_coverage=.2,global_rmse=.3,defect_region_rmse=.4))
    result=object_aggregate(rows)
    assert len(result)==2*len(CHECKPOINTS)*len(POLICIES)
    assert all(r['n_models']==2 for r in result)


def test_actual_12cubed_geometry_policy_direction_if_available():
    try:
        from experiment_08z import geometry_and_coverage, SIZE, WARM, BATCH, POOL
        A,warm,seed=geometry_and_coverage()
    except ImportError:
        pytest.skip('project geometry dependencies not present in this local snapshot')
    full,_=select_full(A,None,warm,BUDGET,seed,warm_rays=WARM,batch=BATCH,candidate_pool=POOL)
    new,_=select_full_spatial(A,None,warm,BUDGET,seed)
    assert not np.array_equal(full,new)
    for k in CHECKPOINTS:
        assert sensitivity_gini(A,new[:k])<sensitivity_gini(A,full[:k])
