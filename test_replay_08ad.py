"""Tests for independent voxel replay; tiny manufactured fixtures are not 08AC evidence."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from scipy import sparse
import replay_08ad as r


def test_independent_mart_matches_scalar_manual_update():
    a=sparse.csr_matrix([[2.,0.],[0.,2.]])
    x=r.independent_mart(a,[1.2,1.2],epochs=1,relaxation=.25)
    assert np.allclose(x, [.3*2**.25,.3*2**.25])


def test_mart_observation_order_and_empty_row():
    a=sparse.csr_matrix([[1.,1.],[2.,0.],[0.,0.]])
    x=r.independent_mart(a,[.5,.2,0],epochs=5)
    assert x.shape==(2,) and np.all(np.isfinite(x)) and np.all(x>0)
    with pytest.raises(ValueError):r.independent_mart(a,[-1,.2,0])
    with pytest.raises(ValueError):r.independent_mart(a,[1.])


def test_voxel_error_partition():
    err=r.independent_errors([1,3,4],[1,2,0],[0,1,0])
    assert err['global_rmse']==pytest.approx(np.sqrt(17/3))
    assert err['defect_region_rmse']==pytest.approx(1.)
    assert err['nondefect_rmse']==pytest.approx(np.sqrt(8.))


def test_independent_noise_deterministic_nonnegative():
    c=np.arange(15,dtype=float)
    x=r.independently_noisy(c,123)
    assert np.array_equal(x,r.independently_noisy(c,123))
    assert x.shape==c.shape and np.all(x>=0)
    with pytest.raises(ValueError):r.independently_noisy([-1,0],123)


def write_csv(file, data):
    with file.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)


def make_orders_fixture(tmp_path):
    archive=tmp_path/'archive';archive.mkdir()
    indexes=[]
    pf={'order_sha256':{}}
    for seed in r.SEEDS:
        pf['order_sha256'][str(seed)]={}
        ids=np.arange(r.BUDGET,dtype=np.int64)
        for pol in r.POLICIES:
            d=r.order_digest(ids)
            pf['order_sha256'][str(seed)][pol]=d
            indexes.extend([{'acquisition_seed':seed,'policy':pol,'acquired_index':i+1,'ray_id':int(k),'order_sha256':d}
                            for i,k in enumerate(ids)])
    write_csv(archive/'acquisition_orders.csv',indexes)
    return archive,pf


def test_frozen_order_groups_hashes_and_warm_prefix(tmp_path):
    archive,pf=make_orders_fixture(tmp_path)
    groups=r.archived_orders(archive,pf,r.BUDGET+100)
    assert len(groups)==8
    assert all(len(x)==1024 for x in groups.values())
    with (archive/'acquisition_orders.csv').open(newline='') as f:data=list(csv.DictReader(f))
    data[0]['ray_id']='1000'
    write_csv(archive/'acquisition_orders.csv',data)
    with pytest.raises(RuntimeError,match='invalid ray order|fingerprint mismatch'):
        r.archived_orders(archive,pf,r.BUDGET+100)


def test_prefix_fingerprints_enforced(tmp_path):
    archive,pf=make_orders_fixture(tmp_path)
    groups=r.archived_orders(archive,pf,r.BUDGET+100)
    write_csv(archive/'prefix_reconstructions.csv',[{'object_id':'test','acquisition_seed':r.SEEDS[0],
        'model':'same','policy':'coverage','acquired':512,'order_sha256':'f'*64}])
    with pytest.raises(RuntimeError,match='prefix order hash mismatch'):
        r.stored_records(archive,groups)


def test_refuse_existing_output(tmp_path):
    output=tmp_path/'existing';output.mkdir()
    with pytest.raises(FileExistsError):r.replay(tmp_path,tmp_path,tmp_path,output)


def test_independent_kernel_against_repository_reference():
    """Production function imported ONLY in the test, never by the replay script."""
    import sys
    here=Path(__file__).resolve().parent
    if not (here/'experiment_05b_mart.py').exists() and not (here/'rbyrct-3d-05a'/'experiment_05b_mart.py').exists():
        pytest.skip('Production repository MART module not available for parity test')
    if (here/'rbyrct-3d-05a').exists():sys.path.insert(0,str(here/'rbyrct-3d-05a'))
    from experiment_05b_mart import mart_reconstruct
    rng=np.random.default_rng(333)
    a=sparse.random(13,31,density=.18,random_state=12,format='csr',data_rvs=lambda n:rng.uniform(.02,2,n))
    b=rng.uniform(.01,5,13)
    ours=r.independent_mart(a,b,epochs=3,relaxation=.25)
    original=mart_reconstruct(a,b,epochs=3,relaxation=.25)
    assert np.allclose(ours,original,rtol=1e-13,atol=1e-13)


def test_independent_noise_against_repository_reference():
    """Check RNG policy while keeping replay's implementation independent."""
    import sys
    here=Path(__file__).resolve().parent
    if not (here/'experiment_05b_08b.py').exists() and not (here/'rbyrct-3d-05a'/'experiment_05b_08b.py').exists():
        pytest.skip('Production noise module not available for parity test')
    if (here/'rbyrct-3d-05a').exists():sys.path.insert(0,str(here/'rbyrct-3d-05a'))
    from experiment_05b_08b import nonnegative_noisy_measurements
    clean=np.array([0.,.02,.5,1.,10.,25.])
    assert np.allclose(r.independently_noisy(clean,991),nonnegative_noisy_measurements(clean,.005,991),rtol=0,atol=0)
