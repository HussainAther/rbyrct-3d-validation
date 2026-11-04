"""08L saved-output auditor tests, including corrupted-file rejection."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from audit_08l import audit,digest_order,near
POLICIES = ("coverage", "gradient", "incremental_25", "information_diag")


def csvout(path,records):
    with path.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)

def fixture(tmp_path):
    p=tmp_path/'original';p.mkdir()
    protocol=dict(sizes=[4],object_seeds={'4':[1001,1002]},models=['same','independent'],
        policies=list(POLICIES),configs={'4':dict(budget=8,checkpoints=[4,8],warm=2)},
        angles=4,tilts=[0,1],acquisition_seed=502,factor=2,
        information_score='hypothetical geometry-only diagonal covariance reduction')
    (p/'protocol.json').write_text(json.dumps(protocol))
    (p/'environment.json').write_text('{}')
    orders=[];prefix=[];man=[];obs=[]
    for seed in (1001,1002):
        oid=f'defect_dev_{seed}'
        man.append(dict(size=4,object_id=oid,object_seed=seed,mask_voxels=4,
                        mask_sha256='a'*64,truth_sha256='b'*64,n_defects=2))
        for model in ('same','independent'):
            ids={'coverage':list(range(8)), 'gradient':[0,1,9,10,11,12,13,14],
                 'incremental_25':[0,1,8,9,10,11,12,13], 'information_diag':[0,1,15,16,17,18,19,20]}
            for policy,order in ids.items():
                for index,ray in enumerate(order,1):
                    orders.append(dict(size=4,object_id=oid,model=model,policy=policy,acquired_index=index,ray_id=ray))
                for budget in (4,8):
                    base=.4 if budget==4 else .2
                    factor={'coverage':1,'gradient':1.1,'incremental_25':1.03,'information_diag':.95}[policy]
                    prefix.append(dict(size=4,object_id=oid,object_seed=seed,model=model,acquisition_seed=506,
                        policy=policy,acquired=budget,global_rmse=base*factor,defect_region_rmse=base*2*factor,
                        nondefect_rmse=base*.8*factor,gain_vs_coverage=1-factor,
                        defect_gain_vs_coverage=1-factor,nondefect_gain_vs_coverage=1-factor,
                        shared_with_coverage=len(set(order[:budget])&set(ids['coverage'][:budget])),
                        order_sha256=digest_order(order[:budget]),selection_seconds=0.1,reconstruction_seconds=0.2,
                        guard_binding_choices=2 if policy=='incremental_25' else 0,
                        guard_intervention_choices=1 if policy=='incremental_25' else 0))
            obs.append(dict(size=4,object_id=oid,model=model,trace_json=json.dumps({'choices':1})))
    csvout(p/'acquisition_orders.csv',orders)
    csvout(p/'prefix_reconstructions.csv',prefix)
    csvout(p/'object_manifest.csv',man)
    csvout(p/'guard_batch_audit.csv',obs)
    obj=[]
    for seed in (1001,1002):
        for budget in (4,8):
            for policy in POLICIES:
                group=[r for r in prefix if r['object_seed']==seed and r['acquired']==budget and r['policy']==policy]
                obj.append(dict(size=4,object_id=f'defect_dev_{seed}',acquired=budget,policy=policy,
                    n_conditions=2,mean_global_gain=group[0]['gain_vs_coverage'],
                    mean_defect_gain=group[0]['defect_gain_vs_coverage'],
                    mean_nondefect_gain=group[0]['nondefect_gain_vs_coverage']))
    csvout(p/'object_level_summary.csv',obj)
    ag=[]
    for budget in (4,8):
        for policy in POLICIES:
            group=[r for r in obj if r['acquired']==budget and r['policy']==policy]
            ag.append(dict(size=4,acquired=budget,policy=policy,n_objects=2,
                mean_global_gain=group[0]['mean_global_gain'],mean_defect_gain=group[0]['mean_defect_gain'],
                object_global_wins=sum(x['mean_global_gain']>0 for x in group),
                object_defect_wins=sum(x['mean_defect_gain']>0 for x in group)))
    csvout(p/'aggregate_summary.csv',ag)
    (p/'run_status.json').write_text(json.dumps({'complete':True,'completed_histories':16,'completed_reconstructions':32}))
    files=sorted(f for f in p.iterdir() if f.is_file())
    (p/'sha256.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}))
    return p

def test_valid_fixture(tmp_path):
    d=fixture(tmp_path);result=audit(d,expected_full=False)
    assert result['verdict']=='PASS' and result['error_count']==0
    assert result['histories_verified']==16 and result['checkpoint_rows_verified']==32
    assert result['information_orders_identical_by_size']=={'4':True}

def test_hash_tampering_detected(tmp_path):
    d=fixture(tmp_path)
    with (d/'environment.json').open('a') as f:f.write('bad')
    result=audit(d,expected_full=False)
    assert result['verdict']=='FAIL' and any('SHA256 mismatch' in e for e in result['errors'])

def test_wrong_paired_gain_detected_even_with_updated_manifest(tmp_path):
    d=fixture(tmp_path)
    a=list(csv.DictReader((d/'prefix_reconstructions.csv').open(newline='')))
    a[0]['gain_vs_coverage']='0.9'
    csvout(d/'prefix_reconstructions.csv',a)
    h=json.loads((d/'sha256.json').read_text())
    h['prefix_reconstructions.csv']=hashlib.sha256((d/'prefix_reconstructions.csv').read_bytes()).hexdigest()
    (d/'sha256.json').write_text(json.dumps(h))
    result=audit(d,expected_full=False)
    assert result['verdict']=='FAIL' and any('incorrect paired gain' in e for e in result['errors'])

def test_information_order_mutation_detected(tmp_path):
    d=fixture(tmp_path)
    order=list(csv.DictReader((d/'acquisition_orders.csv').open(newline='')))
    r=next(r for r in order if r['policy']=='information_diag' and r['object_id']=='defect_dev_1002' and r['model']=='same' and r['acquired_index']=='8')
    r['ray_id']='21'
    csvout(d/'acquisition_orders.csv',order)
    h=json.loads((d/'sha256.json').read_text());h['acquisition_orders.csv']=hashlib.sha256((d/'acquisition_orders.csv').read_bytes()).hexdigest()
    (d/'sha256.json').write_text(json.dumps(h))
    result=audit(d,expected_full=False)
    assert result['verdict']=='FAIL' and result['information_orders_identical_by_size']=={'4':False}

def test_nonfinite_gain_detected(tmp_path):
    d=fixture(tmp_path)
    a=list(csv.DictReader((d/'prefix_reconstructions.csv').open(newline='')))
    a[0]['global_rmse']='nan';csvout(d/'prefix_reconstructions.csv',a)
    with pytest.raises(ValueError,match='nonfinite'):audit(d,expected_full=False)

def test_sha256_integer_order_is_little_endian():
    ids=[1,2,65536]
    assert digest_order(ids)==hashlib.sha256(np.asarray(ids,dtype='<i8').tobytes()).hexdigest()

def test_near_tolerance():
    assert near(0.1+0.2,0.3)
    assert not near(.2,.3)
