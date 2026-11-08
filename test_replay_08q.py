"""Focused 08Q tests. Full archive-driven replay runs on the user's Windows machine."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

from replay_08q import (replay_mart, voxel_rmse, summarize, order_digest,
                        load_orders, verify_inputs, digest_file)


def test_mart_one_row_manual():
    a=sparse.csr_matrix([[2.,1.,0.]])
    b=np.array([1.2])
    actual=replay_mart(a,b,epochs=1,initial=.3,relaxation=.25)
    ratio=1.2/(.3*3)
    expected=np.array([.3*ratio**.25,.3*ratio**.125,.3])
    np.testing.assert_allclose(actual,expected,rtol=1e-14,atol=1e-14)


def test_mart_matches_frozen_reference_multiple_epochs():
    from experiment_05b_mart import mart_reconstruct
    a=sparse.csr_matrix(np.array([[1,2,0,0],[0,1,1,2],[3,0,0,1],
                                  [0,0,0,0],[.3,.7,.2,.1]],dtype=float))
    b=np.array([1.,.7,1.8,0.,.25])
    for epochs in (1,3,16):
        replay=replay_mart(a,b,epochs=epochs,relaxation=.25)
        frozen=mart_reconstruct(a,b,epochs,relaxation=.25)
        np.testing.assert_allclose(replay,frozen,rtol=1e-13,atol=1e-13)


def test_mart_changes_when_data_changes():
    a=sparse.csr_matrix([[1.,2.],[2.,1.]])
    x=replay_mart(a,[.6,1.],epochs=3)
    y=replay_mart(a,[.7,1.],epochs=3)
    assert not np.array_equal(x,y)


@pytest.mark.parametrize('b', [[-1.], [float('nan')]])
def test_mart_rejects_invalid_measurements(b):
    with pytest.raises(ValueError):replay_mart(sparse.csr_matrix([[1.,1.]]),b)


def test_independent_voxel_rmse():
    x=np.array([1.,0.,3.,2.]); truth=np.array([0.,1.,2.,4.]); mask=[True,False,True,False]
    got=voxel_rmse(x,truth,mask)
    assert got['global_rmse']==pytest.approx(np.sqrt(7/4))
    assert got['defect_region_rmse']==pytest.approx(1.)
    assert got['nondefect_rmse']==pytest.approx(np.sqrt(5/2))


def test_object_level_averaging():
    rows=[]
    for obj in range(8):
        for model in ('same','independent'):
            for seed in (11,22):
                rows.append(dict(object_id=f'defect_validation_{obj}',model=model,
                    acquisition_seed=seed,acquired=2048,global_gain=.05+obj*.001,
                    defect_gain=.07+obj*.002))
    objs,agg=summarize(rows)
    assert len(objs)==8 and agg[0]['n_objects']==8
    assert agg[0]['mean_global_gain']==pytest.approx(.0535)
    assert agg[0]['mean_defect_gain']==pytest.approx(.077)
    assert agg[0]['object_global_wins']==8


def test_summary_rejects_pseudoreplication():
    rows=[dict(object_id='a',model='same',acquisition_seed=1,acquired=2048,global_gain=.1,defect_gain=.1)]*4
    with pytest.raises(ValueError):summarize(rows)


def test_order_sha_equivalent_to_little_endian_int64():
    ids=[0,17,200,4095]
    assert order_digest(ids)==hashlib.sha256(np.array(ids,dtype='<i8').tobytes()).hexdigest()


def test_load_orders_rejects_duplicate_or_incomplete(tmp_path):
    with (tmp_path/'acquisition_orders.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['object_id','model','acquisition_seed','policy','acquired_index','ray_id'])
        writer.writeheader();writer.writerow(dict(object_id='defect_validation_1',model='same',
            acquisition_seed=33,policy='coverage',acquired_index=1,ray_id=1))
    with pytest.raises(ValueError):load_orders(tmp_path,dict(objects=[1],models=['same'],acquisition_seeds=[1]))


def test_protocol_lock_mismatch_fails_closed(tmp_path):
    path=tmp_path/'lock.json';path.write_text('{}',encoding='utf8')
    with pytest.raises(ValueError):verify_inputs(tmp_path,path,tmp_path)


def test_archived_file_digest_changes_on_tamper(tmp_path):
    f=tmp_path/'x';f.write_text('one')
    old=digest_file(f);f.write_text('two')
    assert digest_file(f)!=old
