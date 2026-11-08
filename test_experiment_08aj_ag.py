import json
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csr_matrix
import experiment_08aj_ag as ag
import experiment_08aj_ad as ad


def fixture(tmp_path,monkeypatch):
    root=tmp_path/'ag';src=tmp_path/'source';src.mkdir()
    A=csr_matrix(np.array([[1.,.5]+[0.]*6,[.5,1.]+[0.]*6],dtype=float))
    y=np.array([.6,.4]);reference=np.full(8,.3)
    for i in range(8):ad.step_row(reference,A,y,i%2,.25)
    for k,v in {'csr_data.npy':A.data,'csr_indices.npy':A.indices,'csr_indptr.npy':A.indptr,
                'measurements.npy':y,'reconstruction.npy':reference,'order.npy':np.array([0,1])}.items():
        with (src/k).open('wb') as f:np.save(f,v)
    plan={'schema':ag.SCHEMA,'namespace':'FRESH_ENGINEERING_RECOVERY_ONLY','n':2,'budget':2,
          'epochs':4,'relaxation':.25,'policy':'information_diag','model':'same','checkpoint_step_rows':2,
          'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    root.mkdir();(root/'checkpoints').mkdir();ad.create(root/'plan.json',ad.canonical(plan))
    def fake_verify(out,*args):
        p=ad.load_receipt(Path(out)/'plan.json');done,x,prev=ad.verify_chain(out,p)
        return p,src,done,x,prev
    monkeypatch.setattr(ag,'verify',fake_verify)
    return root,src,plan

def test_row_resume_matches_uninterrupted(tmp_path,monkeypatch):
    root,src,p=fixture(tmp_path,monkeypatch)
    assert ag.run(root,None,None,None,stop_after_rows=3)['rows_done']==3
    out=ag.run(root,None,None,None)
    assert out['verdict']=='AG_FRESH_ENGINEERING_RESUME_PASS'
    assert np.array_equal(np.load(root/'final_reconstruction.npy'),np.load(src/'reconstruction.npy'))

def test_early_audit_is_failure(tmp_path,monkeypatch):
    root,_,p=fixture(tmp_path,monkeypatch)
    from experiment_08aj_ag_audit import audit
    monkeypatch.setattr(ag,'verify',lambda *args:(p,None,0,None,'GENESIS'))
    assert audit(root,None,None,None)['pass'] is False

def test_corrupt_snapshot_fails_closed(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path,monkeypatch)
    ag.run(root,None,None,None,stop_after_rows=3)
    cp=root/'checkpoints'/'cp_00000003.npy';cp.write_bytes(cp.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='chain/hash'):ag.run(root,None,None,None)

def test_modified_checkpoint_receipt_fails_closed(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path,monkeypatch);ag.run(root,None,None,None,stop_after_rows=3)
    f=root/'checkpoints'/'cp_00000003.json';obj=json.loads(f.read_bytes());obj['rows_done']=4
    f.write_bytes(ad.canonical(obj))
    with pytest.raises(ValueError):ag.run(root,None,None,None)

def test_orphan_checkpoint_fails_closed(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path,monkeypatch)
    (root/'checkpoints'/'unknown.npy').write_bytes(b'broken')
    with pytest.raises(ValueError,match='orphan'):ag.run(root,None,None,None)

def test_invalid_wall_guard(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='wall budget'):ag.run(root,None,None,None,wall_seconds=0)

def test_invalid_stop_count(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='positive'):ag.run(root,None,None,None,stop_after_rows=0)

def test_existing_evidence_cannot_be_overwritten(tmp_path,monkeypatch):
    root,_,_=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(ag,'expected_plan',lambda *args:{})
    with pytest.raises(FileExistsError):ag.initialize(root,None,None,None,'information_diag','same')

def test_prospective_cohort_locked():
    assert 'production-run' not in ag.__doc__
    assert ag.SCHEMA.endswith('-v1')

def test_ag_initialization_only_fixed_af_inputs(tmp_path,monkeypatch):
    monkeypatch.setattr(ag,'expected_plan',lambda *args:{'schema':ag.SCHEMA,'n':8,'epochs':2,'production_execution_allowed':False})
    out=ag.initialize(tmp_path/'ag',None,None,None,'information_diag','same')
    assert out['production_execution_allowed'] is False
    assert ad.load_receipt(tmp_path/'ag'/'plan.json')['production_execution_allowed'] is False
