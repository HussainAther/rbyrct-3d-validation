import csv
import json
import numpy as np
import pytest
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_gate import AcquiredOnly
from experiment_08b import select_incremental,run


def fixture():
    n=4; angles=2; seed=808311
    A=system_matrix(n,angles,TILTS).tocsr()
    warm=voxel_coverage_order(A,n,angles,len(TILTS),40,seed,8)
    measured=np.asarray(A @ (.1+.5*np.random.default_rng(808221).random(n**3))).ravel()
    return A,warm,measured,n,angles,seed


def acquire(A,warm,measured,n,angles,seed):
    o=AcquiredOnly(measured);o.commit(warm[:8])
    order,trace,seconds=select_incremental(A,o,n,angles,warm,40,seed,
        warm_rays=8,batch=4,candidate_pool=8,provisional_epochs=1)
    return o,order,trace,seconds


def test_acquired_only_and_unique_history():
    A,warm,measured,n,angles,seed=fixture()
    o,order,trace,s=acquire(A,warm,measured,n,angles,seed)
    assert len(order)==40 and len(np.unique(order))==40
    assert o.allowed==set(map(int,order))
    assert np.array_equal(order[:8],warm[:8]) and len(trace)==8
    assert all(r['min_eligible']>=1 for r in trace)
    assert s>=0


def test_repeat_deterministically():
    args=fixture()
    assert np.array_equal(acquire(*args)[1],acquire(*args)[1])


def test_fail_closed_unacquired_observation():
    A,warm,measured,n,angles,seed=fixture()
    oracle=AcquiredOnly(measured)
    oracle.commit(warm[:8])
    with pytest.raises(AssertionError):
        _=oracle[[int(warm[9])]]


def test_invalid_configuration_and_warm_duplicates():
    A,warm,measured,n,angles,seed=fixture()
    oracle=AcquiredOnly(measured);oracle.commit(warm[:8])
    kwargs=dict(warm_rays=8,batch=4,candidate_pool=8,provisional_epochs=1)
    with pytest.raises(ValueError):
        select_incremental(A,oracle,n,angles,warm,40,seed,lam=-.1,**kwargs)
    dup=np.asarray(warm).copy();dup[1]=dup[0]
    with pytest.raises(ValueError):
        select_incremental(A,oracle,n,angles,dup,40,seed,**kwargs)


def test_file_outputs_no_overwrite_and_mechanics(tmp_path):
    config={4:dict(budget=40,warm=8,batch=4,pool=8,epochs=1)}
    out=tmp_path/'development'
    rows=run(out,sizes=(4,),signal_seeds=(808221,),configs=config)
    assert len(rows)==3
    assert set(x['policy'] for x in rows)=={'coverage','gradient','incremental_25'}
    assert rows[-1]['guard_binding_choices']>0
    for name in ('acquisition_orders.csv','incremental_batch_audit.csv','policy_summary.csv','protocol.json','sha256.json'):
        assert (out/name).exists()
    with (out/'policy_summary.csv').open(newline='') as f:
        assert len(list(csv.DictReader(f)))==3
    with (out/'protocol.json').open() as f:
        assert json.load(f)['guard_lambda']==.25
    with pytest.raises(FileExistsError):run(out,sizes=(4,),signal_seeds=(808221,),configs=config)
