"""08M0 synthetic engineering tests; no defect truth or reconstruction used."""
import hashlib
import json
import numpy as np
import pytest
from scipy import sparse
from experiment_08m0 import (CommitOnly, CHECKPOINTS, order_sha256,
                            validate_order, run)


def test_commit_only_refuses_detector_reads():
    gate=CommitOnly()
    gate.commit([4,5])
    assert gate.committed==[4,5]
    with pytest.raises(AssertionError):gate[4]
    with pytest.raises(AssertionError):gate.measurements


def test_digest_stable_and_order_sensitive():
    assert order_sha256([1,2,3])==order_sha256(np.array([1,2,3],dtype='int64'))
    assert order_sha256([1,2,3])!=order_sha256([2,1,3])


def test_validate_order_and_checkpoints():
    gate=CommitOnly();gate.commit(range(3,12))
    hashes=validate_order(range(12),range(3),12,20,gate)
    assert hashes=={}  # miniature budgets do not reach frozen checkpoints
    with pytest.raises(ValueError):validate_order([0,1,2,2],range(3),4,20,gate)


def test_reject_wrong_commit_sequence():
    gate=CommitOnly();gate.commit([4,3])
    with pytest.raises(ValueError):validate_order([0,1,2,3,4],[0,1,2],5,12,gate)


def fake_matrix(n,angles,tilts):
    row_count=n*n*angles*len(tilts)
    rng=np.random.default_rng(823)
    rows=np.repeat(np.arange(row_count),2)
    cols=rng.integers(0,n**3,size=len(rows))
    vals=rng.uniform(.1,1.,size=len(rows))
    return sparse.coo_matrix((vals,(rows,cols)),shape=(row_count,n**3)).tocsr()


def fake_coverage(A,n,angles,tilt_count,budget,seed,pool):
    return np.arange(budget,dtype=np.int64)


def fake_selector(A,gate,n,angles,warm_order,budget,seed,*,warm_rays,batch,candidate_pool,prior_variance,observation_variance):
    result=np.concatenate([warm_order[:warm_rays],np.arange(budget-1,warm_rays-1,-1)]).astype(int)
    for i in range(warm_rays,budget,batch):gate.commit(result[i:i+batch])
    return result,[],.001


def trial(out,**kwargs):
    return run(out,size=4,angles=2,budget=24,warm_rays=4,batch=4,pool=5,
        seed=811011,repeats=2,matrix_builder=fake_matrix,coverage_builder=fake_coverage,
        selector=fake_selector,tilts=(0.,1.),prior_variance=1.,observation_variance=1.,
        allow_test_scale=True,**kwargs)


def test_synthetic_end_to_end_and_manifest(tmp_path):
    out=tmp_path/'trial'
    profile=trial(out)
    status=json.loads((out/'run_status.json').read_text())
    assert status['complete'] and status['completed_repeats']==2
    assert profile['repeat_full_order_identical'] and profile['nnz']>0
    assert len((out/'engineering_manifest.sha256').read_text().splitlines())==5
    assert len(json.loads((out/'order_fingerprints.json').read_text()))==2


def test_no_overwrite(tmp_path):
    out=tmp_path/'trial'
    trial(out)
    with pytest.raises(FileExistsError):trial(out)


def test_locked_production_arguments(tmp_path):
    with pytest.raises(ValueError):run(tmp_path/'bad',budget=2048)
    with pytest.raises(ValueError):run(tmp_path/'bad2',selector=fake_selector)


def test_geometry_configuration_validation(tmp_path):
    with pytest.raises(ValueError):run(tmp_path/'invalid',size=4,angles=2,budget=1000,
        warm_rays=4,batch=4,pool=5,repeats=2,seed=811011,matrix_builder=fake_matrix,
        coverage_builder=fake_coverage,selector=fake_selector,tilts=(0.,1.),
        prior_variance=1.,observation_variance=1.,allow_test_scale=True)


def test_real_selector_small_sparse_if_importable():
    try:
        from experiment_08k import select_information, ANGLES, TILTS
    except ModuleNotFoundError as exc:
        pytest.skip('full original MART dependencies absent in local snapshot: '+str(exc))
    n=2
    rows=n*n*ANGLES*len(TILTS)
    A=fake_matrix(n,ANGLES,TILTS)
    warm=np.arange(4)
    def once():
        gate=CommitOnly()
        ids,_,_=select_information(A,gate,n,ANGLES,warm,12,123,
            warm_rays=4,batch=2,candidate_pool=6,prior_variance=1.,observation_variance=1.)
        validate_order(ids,warm,12,rows,gate)
        return ids
    assert np.array_equal(once(),once())
