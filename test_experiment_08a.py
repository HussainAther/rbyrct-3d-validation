import numpy as np
import pytest
from scipy.sparse import csr_matrix
from experiment_08a import incremental_variance, incremental_eligibility, compare_guard, run


def small_matrix():
    return csr_matrix(np.array([[.7,0,.2,0],[0,.3,0,.9],[.1,.4,.8,0],[0,.5,0,.2]], dtype=float))


def test_incremental_matches_direct_variance_including_negative():
    A=small_matrix()
    counts=np.array([.5,.2,.7,.1])
    d=incremental_variance(A,np.array([0,1,2,3]),counts)
    direct=np.array([np.var(counts+A.getrow(i).toarray().ravel())-np.var(counts) for i in range(4)])
    assert np.allclose(d,direct,rtol=1e-12,atol=1e-12)
    assert incremental_variance(csr_matrix([[1,0],[0,1]]),[1],np.array([1.,0.]))[0] == pytest.approx(-.25)


def test_invariance_to_positive_global_scaling_of_ray_and_counts():
    A=small_matrix(); c=np.array([.5,.2,.7,.1]); pool=[0,1,2]
    d=incremental_variance(A,pool,c)
    ds=incremental_variance(A*17,pool,c*17)
    assert np.allclose(ds,d*17**2)
    for fraction in [0,.25,1]:
        assert np.array_equal(incremental_eligibility(d,1,fraction)[0], incremental_eligibility(ds,1,fraction)[0])


def test_reference_admitted_monotonicity_and_endpoints():
    d=np.array([-2.,-1.,0.,1.])
    masks=[incremental_eligibility(d,2,x)[0] for x in [0,.1,.25,.5,1]]
    assert all(m[2] for m in masks)
    assert all(np.all(a<=b) for a,b in zip(masks,masks[1:]))
    assert np.array_equal(masks[0],[True,True,True,False])
    assert masks[-1].all()


def test_flat_delta_pool_admits_all_and_rejects_bad_parameters():
    assert incremental_eligibility([.02,.02,.02],0,.25)[0].all()
    for frac in [-.1,1.1,float('nan')]:
        with pytest.raises(ValueError):incremental_eligibility([0,1],0,frac)
    with pytest.raises(ValueError):incremental_eligibility([0,1],2,.25)
    with pytest.raises(ValueError):incremental_variance(small_matrix(),[0,0],np.zeros(4))


def test_reference_scorer_and_frozen_old_rule_remain_comparable():
    A=small_matrix()
    out=compare_guard(A,np.array([0,1,2,3]),np.array([.1,.3,.1,.4]),np.zeros(1),2)
    assert out['pool_size']==4
    assert 1<=out['old_eligible']<=4 and 1<=out['new_eligible']<=4
    assert out['delta_range']>=0


def test_small_geometry_only_smoke_and_no_overwrite(tmp_path):
    folder=tmp_path/'new'
    rows=run(folder,states={12:(8,)},replicates=1,pool=4)
    assert len(rows)==1 and rows[0]['pools']==1
    for name in ('candidate_pool_diagnostics.csv','summary.csv','protocol.json','sha256.json'):
        assert (folder/name).is_file()
    with pytest.raises(FileExistsError):run(folder,states={12:(8,)},replicates=1,pool=4)
