"""Focused tests for the independent 08AA saved-output auditor."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import pytest
from experiment_08aa import (
    POLICIES, CHECKPOINTS, SEEDS, MODELS, BUDGET, sha_order,
    close, gini, entropy, orders_from_csv, check_rows,
    objects_from_records, check_object_tables, sha_manifest, inspect_manifest,
    audit, emit_csv
)
from scipy.sparse import csr_matrix


def test_order_hash_little_endian():
    assert sha_order([1,2,3])==hashlib.sha256(np.asarray([1,2,3],dtype='<i8').tobytes()).hexdigest()


def test_close_rejects_wrong_value():
    assert close(.2,.2)
    assert not close(.2,.22)


def test_gini_equal():
    assert gini(csr_matrix([[1.,1.,1.]]),[0])==pytest.approx(0)


def test_gini_unequal():
    assert gini(csr_matrix([[4.,0.,0.,0.]]),[0])==pytest.approx(.75)


def test_entropy_uniform():
    assert entropy([0,1,2,3],4)==pytest.approx(1)


def test_entropy_concentrated():
    assert entropy([0,0,0],4)==pytest.approx(0)


def make_archive(root):
    root.mkdir()
    orders={p:[int(x) for x in range(BUDGET)] for p in POLICIES}
    order_rows=[]
    for p,ray_ids in orders.items():
        for i,rid in enumerate(ray_ids):
            order_rows.append(dict(policy=p,acquired_index=i+1,ray_id=rid,order_sha256=sha_order(ray_ids)))
    emit_csv(root/'acquisition_orders.csv',order_rows)
    recon=[]
    multipliers={'coverage':1.,'information_diag':.96,'information_full':1.05,'full_spatial_balanced':.94}
    for seed in SEEDS:
        for m in MODELS:
            for p in POLICIES:
                for k in CHECKPOINTS:
                    ref=(1.+seed%3*.01 + .003*(m=='independent'))*(1. if k==144 else .7)
                    v=ref*multipliers[p]
                    recon.append(dict(object_id=f'defect_dev_{seed}',object_seed=seed,model=m,policy=p,acquired=k,
                         global_rmse=v,defect_region_rmse=v*1.4,nondefect_rmse=v*.8,
                         gain_vs_coverage=1-multipliers[p],defect_gain_vs_coverage=1-multipliers[p],
                         nondefect_gain_vs_coverage=1-multipliers[p],order_sha256=sha_order(orders[p][:k]),
                         selection_seconds=.2,reconstruction_seconds=.3))
    emit_csv(root/'prefix_reconstructions.csv',recon)
    keyed={(r['object_id'],r['model'],r['policy'],int(r['acquired'])):r for r in recon}
    objects=objects_from_records(keyed)
    emit_csv(root/'object_level_summary.csv',list(objects.values()))
    aggregates=[]
    for k in CHECKPOINTS:
        for p in POLICIES:
            z=[objects[(f'defect_dev_{seed}',k,p)] for seed in SEEDS]
            aggregates.append(dict(size=12,acquired=k,policy=p,n_objects=4,
                mean_global_gain=np.mean([q['mean_global_gain'] for q in z]),
                mean_defect_gain=np.mean([q['mean_defect_gain'] for q in z]),
                object_global_wins=sum(q['mean_global_gain']>0 for q in z),
                object_defect_wins=sum(q['mean_defect_gain']>0 for q in z)))
    emit_csv(root/'aggregate_summary.csv',aggregates)
    pair=[]
    for k in CHECKPOINTS:
        for seed in SEEDS:
            oid=f'defect_dev_{seed}'
            a=objects[(oid,k,'full_spatial_balanced')];b=objects[(oid,k,'information_full')]
            pair.append(dict(object_id=oid,acquired=k,
                spatial_minus_full_global_rmse=a['mean_global_rmse']-b['mean_global_rmse'],
                spatial_minus_full_defect_rmse=a['mean_defect_rmse']-b['mean_defect_rmse'],
                spatial_better_global=int(a['mean_global_rmse']<b['mean_global_rmse']),
                spatial_better_defect=int(a['mean_defect_rmse']<b['mean_defect_rmse'])))
    emit_csv(root/'spatial_vs_full_object.csv',pair)
    geo=[]
    for k in CHECKPOINTS:
        for p in POLICIES:
            geo.append(dict(policy=p,acquired=k,detector_entropy=entropy(np.arange(k)%144,144),
                detector_bins_visited=min(k,144),weighted_sensitivity_gini=0,
                visited_voxel_fraction=0,overlap_with_full=1.))
    emit_csv(root/'geometry_summary.csv',geo)
    manifest=[]
    for seed in SEEDS:
        manifest.append(dict(object_id=f'defect_dev_{seed}',seed=seed,n_defects=1,mask_voxels=20,
            mask_sha256='a'*64,truth_sha256='b'*64))
    emit_csv(root/'object_manifest.csv',manifest)
    (root/'protocol.json').write_text(json.dumps({'spatial_novelty_weight':.25}))
    (root/'run_status.json').write_text(json.dumps({'complete':True,'completed_reconstructions':64,'expected_reconstructions':64}))
    h={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
    (root/'sha256.json').write_text(json.dumps(h))
    return orders


def test_fully_valid_synthetic_archive(tmp_path):
    root=tmp_path/'archive';orders=make_archive(root)
    assert sha_manifest(root,[],'test')==len(list(root.iterdir()))-1
    errors=[]
    actual=orders_from_csv(root,errors)
    assert orders==actual
    keyed,checks=check_rows(list(csv.DictReader((root/'prefix_reconstructions.csv').open())),actual,errors)
    check_object_tables(root,objects_from_records(keyed),errors)
    inspect_manifest(root,errors)
    assert len(keyed)==64 and checks>100 and not errors
    report=audit(root,None,tmp_path/'audited',geometry=False)
    assert report['complete']


def test_tampered_archive_fails(tmp_path):
    root=tmp_path/'archive';make_archive(root)
    f=root/'aggregate_summary.csv';f.write_text(f.read_text().replace('0.040000000000000036','0.55',1))
    with pytest.raises(RuntimeError):audit(root,None,tmp_path/'audited',geometry=False)
    assert json.loads((tmp_path/'audited'/'audit_report.json').read_text())['complete'] is False


def test_first_vs_second_equal_except_timing(tmp_path):
    root=tmp_path/'second';make_archive(root)
    first=tmp_path/'first';first.mkdir()
    for name in ('protocol.json','acquisition_orders.csv','prefix_reconstructions.csv',
                 'object_manifest.csv','object_level_summary.csv','aggregate_summary.csv','spatial_vs_full_object.csv'):
        (first/name).write_bytes((root/name).read_bytes())
    (first/'run_status.json').write_text(json.dumps({'complete':False,'completed_reconstructions':64,'expected_reconstructions':64}))
    report=audit(root,first,tmp_path/'audited',geometry=False)
    assert report['complete'] and report['failed_attempt_compared']


def test_detects_wrong_prefix_hash(tmp_path):
    root=tmp_path/'archive';make_archive(root)
    p=root/'prefix_reconstructions.csv'
    rows=list(csv.DictReader(p.open()))
    rows[0]['order_sha256']='a'*64
    emit_csv(p,rows)
    with pytest.raises(RuntimeError):audit(root,None,tmp_path/'audited',geometry=False)
