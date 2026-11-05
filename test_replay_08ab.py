"""Unit tests for 08AB's independent voxel-space replay and provenance gates."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

import replay_08ab as r


def toy_matrix():
    return sparse.csr_matrix(np.array([[1., 2., 0.], [0., 1., 1.], [2., 0., 1.]]))


def test_replay_is_deterministic():
    matrix = toy_matrix()
    b = np.array([0.7, 0.4, 0.5])
    assert np.array_equal(r.replay_mart(matrix,b), r.replay_mart(matrix,b))


def test_replay_respects_acquisition_order():
    matrix=toy_matrix()
    b=np.array([1.,0.3,0.5])
    a=r.replay_mart(matrix,b,epochs=1)
    c=r.replay_mart(matrix[[2,0,1]],b[[2,0,1]],epochs=1)
    assert not np.array_equal(a,c)


def test_mart_one_row_analytic():
    matrix=sparse.csr_matrix([[1.,0.]])
    got=r.replay_mart(matrix,np.array([0.6]),epochs=1)
    expected=0.3*np.exp(0.25*np.log(0.6/0.3))
    assert got[0] == pytest.approx(expected)
    assert got[1] == pytest.approx(.3)


def test_mart_zero_observation_is_finite():
    assert np.isfinite(r.replay_mart(toy_matrix(),np.zeros(3),epochs=2)).all()


def test_mart_rejects_negative_measurement():
    with pytest.raises(ValueError):r.replay_mart(toy_matrix(),np.array([1.,-1.,0.]))


def test_mart_rejects_incompatible_dimensions():
    with pytest.raises(ValueError):r.replay_mart(toy_matrix(),np.array([1.,2.]))


def test_voxel_rmse_independent_masks():
    result=r.voxel_rmse(np.array([2.,3.,5.,5.]),np.array([1.,1.,1.,1.]),[True,False,False,True])
    assert result['global_rmse']==pytest.approx(np.sqrt((1+4+16+16)/4))
    assert result['defect_region_rmse']==pytest.approx(np.sqrt((1+16)/2))
    assert result['nondefect_rmse']==pytest.approx(np.sqrt((4+16)/2))


def test_voxel_rmse_rejects_empty_mask():
    with pytest.raises(ValueError):r.voxel_rmse([1.,2.],[1.,2.],[False,False])


def test_order_sha_uses_little_endian_i64():
    values=[2,9,4]
    assert r.order_digest(values)==hashlib.sha256(np.array(values,dtype='<i8').tobytes()).hexdigest()


def test_load_orders_checks_approved_hash(tmp_path):
    filename=tmp_path/'acquisition_orders.csv'
    rows=[];expected={}
    for idx,policy in enumerate(r.POLICIES):
        values=np.arange(r.BUDGET)+idx*300
        expected[policy]=r.order_digest(values)
        rows.extend(dict(policy=policy,acquired_index=j+1,ray_id=int(ray),order_sha256=expected[policy])
                    for j,ray in enumerate(values))
    r.write_csv(filename,rows)
    result=r.load_orders(tmp_path,expected,2000)
    assert len(result)==4
    expected['coverage']='0'*64
    with pytest.raises(RuntimeError,match='SHA-256'):r.load_orders(tmp_path,expected,2000)


def test_load_stored_requires_all_64_rows(tmp_path):
    r.write_csv(tmp_path/'prefix_reconstructions.csv',[dict(object_id='a',model='same',policy='coverage',acquired=144)])
    with pytest.raises(RuntimeError,match='missing/extra'):r.load_stored(tmp_path,{})


def test_verify_archive_rejects_incomplete_manifest(tmp_path):
    a=tmp_path/'archive';a.mkdir()
    p=tmp_path/'preflight';p.mkdir()
    (a/'sha256.json').write_text('{}')
    with pytest.raises(RuntimeError,match='SHA-256 manifest'):r.verify_archive(a,p)


def test_refuse_overwrite_even_on_missing_archive(tmp_path):
    output=tmp_path/'exists';output.mkdir()
    with pytest.raises(FileExistsError):r.replay(tmp_path/'bad',tmp_path/'bad',output)


def test_replay_matches_production_kernel_on_toy():
    # This checks update convention only, not the 08Z archive. Source dependency
    # intentionally imported only in test, never by replay implementation.
    try:
        from experiment_05b_mart import mart_reconstruct
    except ModuleNotFoundError:
        pytest.skip('production kernel unavailable in isolated package tests')
    matrix=toy_matrix()
    b=np.array([.4,.5,.6])
    ours=r.replay_mart(matrix,b,epochs=3,relaxation=.25)
    theirs=mart_reconstruct(matrix,b,3,relaxation=.25)
    np.testing.assert_allclose(ours,theirs,atol=1e-15,rtol=1e-15)
