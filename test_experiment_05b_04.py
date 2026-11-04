"""Tests for the isolated 05B-04 scoring-ablation pilot."""
import numpy as np
import pytest
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_05b_adaptive import adaptive_order
from experiment_05b_04 import select_order, run_case
from experiment_05b_gate import AcquiredOnly


def fixture():
    n=4; angles=2
    A=system_matrix(n,angles,TILTS).tocsr()
    truth=np.full(n**3,.4)
    return A,np.asarray(A@truth).ravel(),truth,n,angles,np.arange(12,dtype=np.int64)


def test_gradient_and_coverage_reproduce_frozen_selector():
    A,obs,truth,n,angles,warm=fixture()
    for policy,strength in [('gradient',1.),('coverage',0.)]:
        expected,_,_=adaptive_order(A,obs,n,angles,warm,20,271828,
                                    warm_rays=12,batch=4,candidate_pool=8,
                                    provisional_epochs=2,feedback_strength=strength,
                                    mart_relaxation=.25)
        actual,_,_=select_order(A,obs,n,angles,warm,20,271828,policy=policy,
                                 warm_rays=12,batch=4,candidate_pool=8,
                                 provisional_epochs=2,relaxation=.25)
        assert np.array_equal(expected,actual)


def test_all_policies_acquired_only():
    A,obs,truth,n,angles,warm=fixture()
    for policy in ('gradient','coverage','capped_gradient','projection_disagreement'):
        guard=AcquiredOnly(obs)
        guard.commit(warm)
        # Guard begins with warm observations only and commits each acquired batch.
        order,_,_=select_order(A,guard,n,angles,warm,20,271828,policy=policy,
                               warm_rays=12,batch=4,candidate_pool=8,
                               provisional_epochs=2,relaxation=.25)
        assert len(set(map(int,order)))==20


def test_invalid_policy_rejected():
    A,obs,truth,n,angles,warm=fixture()
    with pytest.raises(ValueError):
        select_order(A,obs,n,angles,warm,20,271828,policy='oracle',warm_rays=12)
