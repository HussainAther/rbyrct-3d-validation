from pathlib import Path
import json
import numpy as np
import pytest
from experiment_07b import benchmark, csr_bytes, deterministic_signal, validate_config
from scipy.sparse import csr_matrix


def test_manufactured_signal_positive_deterministic():
    a=deterministic_signal(4)
    assert a.shape==(64,) and np.isfinite(a).all() and np.all(a>0)
    assert np.array_equal(a,deterministic_signal(4))


def test_csr_bytes_exact():
    m=csr_matrix(np.array([[1.,0.],[0.,2.]]))
    assert csr_bytes(m)==m.data.nbytes+m.indices.nbytes+m.indptr.nbytes


def test_freeze_production_rejects_overrides():
    with pytest.raises(ValueError,match='fixed'):
        validate_config(16,4,128,32,16,16,2,4,.25,707031,.05,False)


def test_invalid_geometry_rejected():
    with pytest.raises(ValueError):
        validate_config(4,2,100000,12,6,8,1,2,.25,707031,.05,True)


def test_tiny_end_to_end_and_no_overwrite(tmp_path):
    out=tmp_path/'profile'
    stats,rows=benchmark(out,n=4,angles=2,budget=24,warm=8,batch=4,pool=6,
                         provisional_epochs=1,final_epochs=2,allow_test_scale=True)
    assert stats['voxels']==64 and stats['csr_storage_bytes']>0
    assert len(rows)==3 and all(x['unique_rays']==24 for x in rows)
    assert len({x['row_order_sha256'] for x in rows})>=1
    assert set(x['policy'] for x in rows)=={'coverage','gradient','guarded_05'}
    assert (out/'profile.json').exists() and (out/'policy_timing.csv').exists()
    assert json.loads((out/'protocol.json').read_text())['test_scale'] is True
    with pytest.raises(ValueError,match='overwrite'):
        benchmark(out,n=4,angles=2,budget=24,warm=8,batch=4,pool=6,
                  provisional_epochs=1,final_epochs=2,allow_test_scale=True)
