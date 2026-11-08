import json
import numpy as np
import pytest
from experiment_08aj_p2 import check_order, check_prior_fingerprint, validate_finite_reconstruction, run
from experiment_08m0 import order_sha256

def test_order_validation():
    order=check_order([0,1,3,2],[0,1,2,3],4,8,2)
    assert order.tolist()==[0,1,3,2]
    with pytest.raises(ValueError):check_order([0,1,1,2],[0,1,2,3],4,8,2)

def test_order_matches_prior(tmp_path):
    order=np.array([0,1,3,2]);digest=order_sha256(order)
    (tmp_path/'order_fingerprints.json').write_text(json.dumps([{'full_order_sha256':digest}]*2))
    assert check_prior_fingerprint(tmp_path,order)==digest
    with pytest.raises(ValueError):check_prior_fingerprint(tmp_path,[0,1,2,3])

def test_reconstruction_invariant():
    validate_finite_reconstruction(np.ones(8),2)
    with pytest.raises(ValueError):validate_finite_reconstruction(np.array([1.,np.nan]+[1.]*6),2)

def test_pilot_smoke_and_no_overwrite(tmp_path):
    target=tmp_path/'pilot'
    profile=run(target,tmp_path,smoke=True)
    assert profile['complete'] and profile['size']==8
    assert profile['reconstructed_positive_finite']
    assert np.load(target/'reconstruction.npy').shape==(512,)
    assert json.loads((target/'run_status.json').read_text())['complete']
    with pytest.raises(FileExistsError):run(target,tmp_path,smoke=True)
