"""Focused safeguards for frozen RBYRCT-07C2, never run production study."""
import csv
import json
import numpy as np
import pytest
from experiment_07c2 import (validate,run_validation,summarize,OBJECT_SEEDS,PRIMARY,
                             SIZE,BUDGET,POLICIES)
from experiment_06b import defect_phantom
from experiment_07c_preflight import defect_support,error_metrics


def config():
    return dict(size=4,angles=2,factor=2,budget=48,
        checkpoints=(24,36,48),warm=12,batch=6,pool=8,
        provisional_epochs=2,final_epochs=4,relaxation=.25,eta=.05,
        object_seeds=(2077001,),acquisition_seeds=(1901,),models=('same',),
        noise_fraction=.005,offset=.15,step=.25,allow_test_scale=True)


def test_frozen_production_and_seed_separation():
    p=config();p['allow_test_scale']=False
    with pytest.raises(ValueError,match='frozen'):validate(**p)
    p=config();p['object_seeds']=(1066001,)
    with pytest.raises(ValueError,match='reused'):validate(**p)
    assert SIZE==32 and BUDGET==4096 and PRIMARY==2048
    assert len(OBJECT_SEEDS)==8 and POLICIES==('coverage','gradient','guarded_05')


def test_phantom_mask_reproducible_and_truth_separated():
    x,fine,_=defect_phantom(6,2,2077001)
    mask,d=defect_support(6,2,2077001)
    mask2,d2=defect_support(6,2,2077001)
    assert np.array_equal(mask,mask2) and d['mask_sha256']==d2['mask_sha256']
    assert 0<mask.sum()<mask.size and x.size==6**3
    assert fine.shape==(12,12,12)
    met=error_metrics(x,x,mask)
    assert all(v==0 for v in met.values())


def test_summarize_object_replication():
    rows=[]
    for oid in ('a','b'):
        for p in POLICIES:
            for model in ('same','independent'):
                rows.append(dict(object_id=oid,acquired=2048,policy=p,
                   gain_vs_coverage=.1 if p=='guarded_05' else 0.,
                   defect_gain_vs_coverage=.2 if p=='guarded_05' else 0.,
                   nondefect_gain_vs_coverage=.03 if p=='guarded_05' else 0.))
    obj,status=summarize(rows,2048)
    assert len(obj)==6 and status['n_objects']==2
    assert status['primary_object_wins']==2
    assert not status['favorable_primary'] # eight distinct objects required


def test_end_to_end_small_readonly_and_manifest(tmp_path):
    out=tmp_path/'smoke';status=run_validation(out,**config())
    assert status['acquisition_histories']==3
    assert status['reconstructions']==9
    assert status['ray_order_rows']==144
    assert json.loads((out/'run_status.json').read_text())['complete']
    assert (out/'run_manifest.sha256').exists()
    with (out/'prefix_reconstructions.csv').open(newline='') as f: rows=list(csv.DictReader(f))
    assert len(rows)==9
    assert all(float(r['defect_region_rmse'])>=0 for r in rows)
    with (out/'acquisition_orders.csv').open(newline='') as f: order=list(csv.DictReader(f))
    assert len(order)==144
    with pytest.raises(ValueError,match='overwrite'):run_validation(out,**config())


def test_invalid_checkpoints():
    p=config();p['checkpoints']=(24,37,48)
    with pytest.raises(ValueError,match='invalid'):validate(**p)
