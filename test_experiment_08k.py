"""08K: acquisition gate, deterministic selection and paired exploratory reports."""
import csv
import json
import numpy as np
import pytest
from scipy import sparse
from experiment_08k import (run,validate,object_summary,POLICIES,CONFIGS,
    select_information,ANGLES,TILTS)

class NoReads:
    def __init__(self): self.committed=[]
    def __getitem__(self,key): raise AssertionError('information selector read measurements')
    def commit(self, ids): self.committed.extend(map(int,ids))

def tiny_geometry(n=2):
    nr=n*n*ANGLES*len(TILTS)
    rng=np.random.default_rng(123)
    a=sparse.random(nr,n**3,density=.45,format='csr',random_state=123)
    a.data=np.abs(a.data)+.01
    return a

def test_information_selector_acquired_only_and_unique():
    A=tiny_geometry();warm=np.arange(4);gate=NoReads()
    order,trace,seconds=select_information(A,gate,2,ANGLES,warm,10,17,
         warm_rays=4,batch=3,candidate_pool=5)
    assert len(order)==10 and len(set(order))==10
    assert np.array_equal(order[:4],warm)
    assert set(gate.committed)==set(order[4:]) and len(gate.committed)==6
    assert trace==[] and seconds>=0

def test_information_selector_reproducible():
    A=tiny_geometry();w=np.arange(4)
    def make():return select_information(A,NoReads(),2,ANGLES,w,12,19,warm_rays=4,batch=2,candidate_pool=6)[0]
    assert np.array_equal(make(),make())

def test_geometry_only_ignores_measurements():
    A=tiny_geometry();w=np.arange(4)
    a=select_information(A,NoReads(),2,ANGLES,w,12,19,warm_rays=4,batch=3,candidate_pool=6)[0]
    b=select_information(A,NoReads(),2,ANGLES,w,12,19,warm_rays=4,batch=3,candidate_pool=6)[0]
    assert np.array_equal(a,b)

def test_bad_parameters_rejected():
    A=tiny_geometry();w=np.arange(4)
    for args in [dict(prior_variance=0),dict(observation_variance=-1),dict(candidate_pool=0),dict(warm_rays=0)]:
        base=dict(warm_rays=4,batch=2,candidate_pool=5);base.update(args)
        with pytest.raises(ValueError):select_information(A,NoReads(),2,ANGLES,w,10,12,**base)

def test_locked_protocol(tmp_path):
    with pytest.raises(ValueError):run(tmp_path/'bad',sizes=(12,))

def test_reserved_seeds_rejected():
    with pytest.raises(ValueError):
        validate((12,),{12:(2077001,)},{12:CONFIGS[12]},('same',),810411)

def test_object_summary_four_policies():
    rows=[dict(size=4,object_id='a',acquired=24,policy=p,
               gain_vs_coverage=0,defect_gain_vs_coverage=0,nondefect_gain_vs_coverage=0)
          for p in POLICIES]
    assert len(object_summary(rows))==4

def test_miniature_end_to_end(tmp_path):
    cfg={4:dict(budget=40,checkpoints=(24,40),warm=8,batch=4,pool=8,epochs=1,final_epochs=2)}
    out=tmp_path/'small'
    summary=run(out,sizes=(4,),object_seeds={4:(810701,)},configs=cfg,
                models=('same',),acquisition_seed=810711,allow_test_scale=True)
    assert len(summary)==8
    status=json.loads((out/'run_status.json').read_text())
    assert status['complete'] and status['completed_histories']==4 and status['completed_reconstructions']==8
    with (out/'prefix_reconstructions.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    assert set(r['policy'] for r in rows)==set(POLICIES)
    for r in rows:
        b=next(x for x in rows if x['policy']=='coverage' and x['acquired']==r['acquired'])
        assert np.isclose(float(r['gain_vs_coverage']),
              (float(b['global_rmse'])-float(r['global_rmse']))/max(float(b['global_rmse']),1e-12))
    with pytest.raises(FileExistsError):
        run(out,sizes=(4,),object_seeds={4:(810701,)},configs=cfg,
            models=('same',),acquisition_seed=810711,allow_test_scale=True)
