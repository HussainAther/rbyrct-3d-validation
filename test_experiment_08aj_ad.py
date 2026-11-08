import json
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csr_matrix
import experiment_08aj_ad as ad

def fake_case(tmp_path,monkeypatch):
    source=tmp_path/'source';source.mkdir();root=tmp_path/'ad'
    A=csr_matrix(np.array([[1.,.5]+[0.]*6,[.5,1.]+[0.]*6],dtype=np.float64))
    y=np.array([.6,.4]);x=np.full(8,.3)
    for i in range(8):ad.step_row(x,A,y,i%2,.25)
    for name,v in {'csr_data.npy':A.data,'csr_indices.npy':A.indices,
                   'csr_indptr.npy':A.indptr,'measurements.npy':y,'reconstruction.npy':x}.items():
        with (source/name).open('wb') as f:np.save(f,v)
    plan={'n':2,'budget':2,'epochs':4,'relaxation':.25,'checkpoint_step_rows':2,'policy':'information_diag','model':'same'}
    plan.update({'schema':ad.SCHEMA,'namespace':'ENGINEERING_SHADOW_ONLY','seed':ad.SEED,
       'ab_plan_sha256':'abc','ab_receipt_sha256':'def','ab_inputs_sha256':{n:ad.sha(source/n) for n in ('csr_data.npy','csr_indices.npy','csr_indptr.npy','measurements.npy','reconstruction.npy')},
       'production_jobs_executed':0,'production_execution_allowed':False,'resource_policy_approved':False,'scientific_signoff':False,'frozen':False,'no_confirmatory_outcomes':True})
    root.mkdir();(root/'checkpoints').mkdir();ad.create(root/'plan.json',ad.canonical(plan))
    monkeypatch.setattr(ad,'check_inputs',lambda *args:(plan,source))
    return root,source,plan

def run(root):return ad.run(root,None,None,None,wall_seconds=30)

def test_row_recurrence_matches_known():
    A=csr_matrix([[1.,0.],[0.,1.]])
    x=np.array([.3,.3]);ad.step_row(x,A,np.array([.6,.15]),0,.25)
    assert x[0]>.3 and x[1]==.3

def test_interruption_and_exact_resume(tmp_path,monkeypatch):
    root,_,p=fake_case(tmp_path,monkeypatch)
    r=ad.run(root,None,None,None,stop_after_rows=3)
    assert r['rows_done']==3
    assert run(root)['verdict']=='AD_ENGINEERING_RESUME_PASS'
    assert np.load(root/'final_reconstruction.npy').shape==(8,)

def test_uninterrupted_same_array(tmp_path,monkeypatch):
    root,source,p=fake_case(tmp_path,monkeypatch)
    assert run(root)['max_abs_error_vs_ab']<1e-12
    assert np.array_equal(np.load(root/'final_reconstruction.npy'),np.load(source/'reconstruction.npy'))

def test_resume_verifies_chain(tmp_path,monkeypatch):
    root,_,p=fake_case(tmp_path,monkeypatch)
    ad.run(root,None,None,None,stop_after_rows=2)
    x=root/'checkpoints'/'cp_00000002.npy';x.write_bytes(x.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='chain/hash'):run(root)

def test_receipt_tampering_rejected(tmp_path,monkeypatch):
    root,_,p=fake_case(tmp_path,monkeypatch)
    ad.run(root,None,None,None,stop_after_rows=2)
    r=root/'checkpoints'/'cp_00000002.json';obj=json.loads(r.read_bytes());obj['rows_done']=1;r.write_bytes(ad.canonical(obj))
    with pytest.raises(ValueError):run(root)

def test_staging_orphan_rejected(tmp_path,monkeypatch):
    root,_,p=fake_case(tmp_path,monkeypatch)
    (root/'checkpoints'/'unexpected.npy').write_bytes(b'bad')
    with pytest.raises(ValueError,match='orphan'):run(root)

def test_noncanonical_plan_rejected(tmp_path):
    path=tmp_path/'p.json';path.write_text('{"a": 1}\n')
    with pytest.raises(ValueError,match='noncanonical'):ad.load_receipt(path)

def test_guard_invalid_timeout(tmp_path,monkeypatch):
    root,_,p=fake_case(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='wall budget'):ad.run(root,None,None,None,wall_seconds=0)

def test_only_fixed_engineering_seed():
    assert ad.SEED==970099
    assert 'production-run' not in ad.__doc__
