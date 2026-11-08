"""05B-05 checks: frozen selection, geometry and offline-only evaluation."""
import numpy as np
import pytest
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_05b_04 import POLICIES, select_order
from experiment_05b_05 import checkpoint_counts, prefix_geometry, evaluate_case
from experiment_05b_gate import AcquiredOnly


def fixture():
    n, angles = 4, 2
    A = system_matrix(n,angles,TILTS).tocsr()
    truth = np.full(n**3,.4)
    observed = np.asarray(A@truth).ravel()
    warm = np.arange(12,dtype=np.int64)
    return A, observed, truth, n, angles, warm


def test_checkpoint_counts_and_invalid_inputs():
    assert checkpoint_counts(12,22,4)==[12,16,20,22]
    with pytest.raises(ValueError):
        checkpoint_counts(20,12,4)


def test_geometry_measures_uncovered_and_view_concentration():
    A,obs,truth,n,angles,warm=fixture()
    one=prefix_geometry(A,warm[:1],n,angles)
    many=prefix_geometry(A,warm,n,angles)
    assert one['largest_view_share']==1.
    assert 0 <= one['touched_voxel_fraction'] <= 1
    assert many['touched_voxel_fraction'] >= one['touched_voxel_fraction']
    assert 0 <= many['view_entropy_normalized'] <= 1+1.e-12


def test_audit_preserves_policy_orders_and_offline_rmse():
    A,obs,truth,n,angles,warm=fixture()
    result=evaluate_case(A,obs,truth,n,angles,warm,271828,20,
        warm_rays=12,batch=4,candidate_pool=8,provisional_epochs=2,
        final_epochs=3,relaxation=.25,feature_cap=3.,checkpoints=[12,16,20])
    for policy in POLICIES:
        expected,_,_=select_order(A,obs,n,angles,warm,20,271828,policy=policy,
            warm_rays=12,batch=4,candidate_pool=8,provisional_epochs=2,relaxation=.25)
        np.testing.assert_array_equal(result['orders'][policy],expected)
    assert len(result['trajectories'])==4*3
    assert len(result['overlaps'])==6*3
    assert len(result['views'])==4*3*angles*len(TILTS)
    for row in result['trajectories']:
        assert np.isfinite(row['rmse'])


def test_selection_only_acquired_measurements_guard():
    A,obs,truth,n,angles,warm=fixture()
    for policy in POLICIES:
        guard=AcquiredOnly(obs)
        guard.commit(warm)
        order,_,_=select_order(A,guard,n,angles,warm,20,271828,policy=policy,
            warm_rays=12,batch=4,candidate_pool=8,provisional_epochs=2,relaxation=.25)
        assert len(order)==20
