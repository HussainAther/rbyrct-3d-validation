"""08Y numerical integrity tests and complete manufactured archive smoke test."""
import csv
import hashlib
import json
import sys
import types

import numpy as np
import pytest
from scipy import sparse

from experiment_08y import (SIZE, ANGLES, TILTS, STUDIES, BUDGET, CHECKPOINTS,
    gini, entropy, center_indices, surrogate_fields, metrics, sha_order,
    load_orders, verified_manifest, validate_reconstruction_records,
    perform, write_csv)


def test_gini_uniform():
    assert gini([2,2,2]) == pytest.approx(0)


def test_gini_zero():
    assert gini([0,0,0]) == 0


def test_gini_concentration():
    assert gini([0,0,3]) == pytest.approx(2/3)


def test_entropy_max_uniform():
    assert entropy([1,1,1,1]) == pytest.approx(1)


def test_entropy_one_bin():
    assert entropy([5,0,0,0]) == pytest.approx(0)


def test_center_cube_geometry_only():
    c=center_indices(12)
    assert c.shape==(12**3,) and int(c.sum())==6**3


def test_precision_surrogate_exact_small():
    A=sparse.csr_matrix([[1., 2.,0.],[0.,3.,4.],[1.,0.,2.]])
    x=surrogate_fields(A,[0,1],prior_variance=2.,observation_variance=4.)
    expect=np.array([.5+1/4,.5+13/4,.5+16/4])
    np.testing.assert_allclose(x['precision'],expect)
    np.testing.assert_allclose(x['variance'],1/expect)
    np.testing.assert_array_equal(x['visits'],[1,2,1])
    np.testing.assert_allclose(x['weighted_sensitivity'],[1,5,4])


def test_reductions_bounds():
    A=sparse.csr_matrix([[1,0,2],[0,0,0]],dtype=float)
    x=surrogate_fields(A,[0],prior_variance=1.,observation_variance=2.)
    assert np.all(x['relative_variance_reduction']>=0)
    assert np.all(x['relative_variance_reduction']<1)
    assert x['relative_variance_reduction'][1]==0


def test_duplicate_rays_rejected():
    with pytest.raises(ValueError):
        surrogate_fields(sparse.eye(3,format='csr'),[0,0],prior_variance=1,observation_variance=1)


def test_invalid_hyperparameters_rejected():
    with pytest.raises(ValueError):
        surrogate_fields(sparse.eye(3,format='csr'),[0],prior_variance=-1,observation_variance=1)


def test_no_defect_truth_required():
    A=sparse.eye(SIZE**3,format='csr')
    result=metrics(A,[0,1,2],size=SIZE,prior_variance=1.,observation_variance=1.)
    assert result['visited_voxel_fraction']==pytest.approx(3/SIZE**3)
    assert 'defect' not in ' '.join(result)


def write_archive(base, study):
    policies,nrecords,nobjects=STUDIES[study]
    base.mkdir()
    orders={p:np.roll(np.arange(BUDGET), i*11).astype(np.int64) for i,p in enumerate(policies)}
    write_csv(base/'acquisition_orders.csv',[
        {'policy':p,'acquired_index':i+1,'ray_id':int(rid),'order_sha256':sha_order(order)}
        for p,order in orders.items() for i,rid in enumerate(order)])
    rec=[]
    for j in range(nobjects):
        for model in ('same','independent'):
            for p in policies:
                for k in CHECKPOINTS:
                    rec.append({'object_id':f'obj{j}','model':model,'policy':p,'acquired':k,
                        'order_sha256':sha_order(orders[p][:k]),'global_rmse':0.1,'defect_region_rmse':0.2})
    write_csv(base/'prefix_reconstructions.csv',rec)
    assert len(rec)==nrecords
    write_csv(base/'aggregate_summary.csv',[
        {'policy':p,'acquired':k,'n_objects':nobjects,
         'mean_global_gain':0.02*i,'mean_defect_gain':0.01*i,
         'object_global_wins':nobjects if i else 0,'object_defect_wins':nobjects if i else 0}
        for i,p in enumerate(policies) for k in CHECKPOINTS])
    (base/'run_status.json').write_text(json.dumps({'complete':True,'completed_reconstructions':nrecords}))
    digest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()}
    (base/'sha256.json').write_text(json.dumps(digest))
    return orders


def test_manifest_tampering_detected(tmp_path):
    src=tmp_path/'archive';write_archive(src,'08U')
    assert verified_manifest(src)==4
    with (src/'run_status.json').open('a') as f:f.write(' ')
    with pytest.raises(ValueError,match='hash mismatch'):
        verified_manifest(src)


def test_order_tampering_detected(tmp_path):
    src=tmp_path/'archive';write_archive(src,'08U')
    rows=list(csv.DictReader((src/'acquisition_orders.csv').open()))
    rows[0]['ray_id']=rows[1]['ray_id']
    write_csv(src/'acquisition_orders.csv',rows)
    with pytest.raises(ValueError):
        load_orders(src,STUDIES['08U'][0],SIZE**3*ANGLES*TILTS)


def test_reconstruction_prefix_tampering_detected(tmp_path):
    src=tmp_path/'archive'; orders=write_archive(src,'08U')
    rows=list(csv.DictReader((src/'prefix_reconstructions.csv').open()))
    rows[0]['order_sha256']='0'*64
    write_csv(src/'prefix_reconstructions.csv',rows)
    with pytest.raises(ValueError,match='fingerprint'):
        validate_reconstruction_records(src,orders,STUDIES['08U'][0],36,3)


def test_end_to_end_synthetic_archives(tmp_path,monkeypatch):
    source={}
    for name in STUDIES:
        root=tmp_path/name
        write_archive(root,name)
        source[name]=root
    A=sparse.eye(SIZE**3,format='csr')
    monkeypatch.setitem(sys.modules,'experiment_04b',types.SimpleNamespace(system_matrix=lambda *args:A))
    monkeypatch.setitem(sys.modules,'experiment_04g',types.SimpleNamespace(TILTS=(0,1,2)))
    report=perform(source,tmp_path/'out',prior_variance=1.,observation_variance=1.)
    assert report['rows']==24
    assert report['comparisons']==18
    assert sum(report['archived_reconstruction_rows_checked'].values())==180
    assert (tmp_path/'out'/'sha256.json').exists()
    with pytest.raises(FileExistsError):
        perform(source,tmp_path/'out',prior_variance=1.,observation_variance=1.)
