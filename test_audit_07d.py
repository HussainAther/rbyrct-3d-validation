import hashlib
import math
import struct
import pytest
from audit_07d import close, fingerprint, gain_from_rmse, weighted_rmse_identity, Checks

def test_negative_gain_is_valid():
    assert close(gain_from_rmse(.1,.14),-.4)
    assert close(gain_from_rmse(.2,.16),.2)

def test_zero_baseline_invalid():
    with pytest.raises(ValueError):gain_from_rmse(0,.1)
    with pytest.raises(ValueError):gain_from_rmse(.1,-.1)

def test_sha256_little_endian_ray_order():
    seq=[1,4,2]
    assert fingerprint(seq)==hashlib.sha256(b''.join(struct.pack('<q',i) for i in seq)).hexdigest()
    assert fingerprint([2,4,1])!=fingerprint(seq)

def test_weighted_regions_exact_identity():
    e=weighted_rmse_identity(math.sqrt(3),1,2,1,2)
    assert close(e,2.5)
    assert not close(3.0,e)

def test_check_collector_flags_without_throw():
    c=Checks();c.ok(True,'good');c.ok(False,'problem')
    assert c.n==2 and c.errors==['problem']

def test_candidate_variance_update_formula():
    import numpy as np
    counts=np.array([.2,1.0,0.,.5])
    ray=np.array([.3,0.,.8,0.])
    centered=counts-counts.mean()
    delta=(2*centered@ray + ray@ray)/len(counts)-(ray.sum()/len(counts))**2
    assert np.isclose(counts.var()+delta,(counts+ray).var(),rtol=1e-12,atol=1e-12)
