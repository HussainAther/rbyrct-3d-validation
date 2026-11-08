import json,os
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csr_matrix
import experiment_08aj_ah as ah
import experiment_08aj_ad as ad
import experiment_08aj_ag as ag
REAL_VERIFY=ah.verify


def small(tmp_path,monkeypatch):
    root=tmp_path/'ah';src=tmp_path/'source';src.mkdir()
    A=csr_matrix(np.array([[1.,.5]+[0.]*6,[.5,1.]+[0.]*6],dtype=float))
    y=np.array([.6,.4]);ref=np.full(8,.3)
    for i in range(8):ad.step_row(ref,A,y,i%2,.25)
    for k,v in {'csr_data.npy':A.data,'csr_indices.npy':A.indices,'csr_indptr.npy':A.indptr,
                'measurements.npy':y,'reconstruction.npy':ref,'order.npy':np.array([0,1])}.items():
        with (src/k).open('wb') as f:np.save(f,v,allow_pickle=False)
    p={'schema':ah.SCHEMA,'namespace':'FRESH_ENGINEERING_RESOURCE_GUARD_ONLY',
       'source':{'n':2,'budget':2,'epochs':4,'relaxation':.25,'policy':'information_diag','model':'same'},
       'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    root.mkdir();(root/'checkpoints').mkdir();ad.create(root/'plan.json',ah.canonical(p))
    def fake_verify(out,*args):
        rp=ah.receipt(Path(out)/'plan.json');n,x,prev=ah.verify_chain(out,rp)
        return rp,src,n,x,prev
    monkeypatch.setattr(ah,'verify',fake_verify)
    return root,src,p

def test_interrupted_resume_exact(tmp_path,monkeypatch):
    root,src,p=small(tmp_path,monkeypatch)
    assert ah.worker_run(root,None,None,None,stop_after_rows=3)['rows_done']==3
    assert ah.worker_run(root,None,None,None)['verdict']=='AH_ENGINEERING_RECOVERY_PASS'
    assert np.array_equal(np.load(root/'final'/'reconstruction.npy'),np.load(src/'reconstruction.npy'))

def test_atomic_checkpoint_has_single_committed_directory(tmp_path,monkeypatch):
    root,_,p=small(tmp_path,monkeypatch)
    ah.worker_run(root,None,None,None,stop_after_rows=3)
    assert sorted(f.name for f in (root/'checkpoints').iterdir())==['cp_00000003']
    assert {x.name for x in (root/'checkpoints'/'cp_00000003').iterdir()}=={'state.npy','receipt.json'}

def test_corrupted_state_rejected(tmp_path,monkeypatch):
    root,_,p=small(tmp_path,monkeypatch);ah.worker_run(root,None,None,None,stop_after_rows=3)
    f=root/'checkpoints'/'cp_00000003'/'state.npy';f.write_bytes(f.read_bytes()+b'bad')
    with pytest.raises(ValueError,match='SHA'):ah.worker_run(root,None,None,None)

def test_uncommitted_staging_fails_closed(tmp_path,monkeypatch):
    root,_,p=small(tmp_path,monkeypatch)
    (root/'checkpoints'/'.stage-crash').mkdir()
    with pytest.raises(ValueError,match='staging'):ah.worker_run(root,None,None,None)

def test_staging_can_be_quarantined_explicitly(tmp_path,monkeypatch):
    root,_,p=small(tmp_path,monkeypatch)
    (root/'checkpoints'/'.stage-crash').mkdir()
    assert ah.quarantine_staging(root)['quarantined']==1
    assert ah.verify_chain(root,p)[0]==0
    assert (root/'quarantine'/'.stage-crash').exists()

def test_orphan_bad_directory_rejected(tmp_path,monkeypatch):
    root,_,p=small(tmp_path,monkeypatch)
    (root/'checkpoints'/'cp_00000004').mkdir()
    with pytest.raises(ValueError):ah.verify_chain(root,p)

def test_modified_receipt_rejected(tmp_path,monkeypatch):
    root,_,p=small(tmp_path,monkeypatch);ah.worker_run(root,None,None,None,stop_after_rows=3)
    f=root/'checkpoints'/'cp_00000003'/'receipt.json';r=ah.receipt(f);r['rows_done']=4
    f.write_bytes(ah.canonical(r))
    with pytest.raises(ValueError):ah.worker_run(root,None,None,None)

def test_no_overwrite_existing_final(tmp_path,monkeypatch):
    root,src,p=small(tmp_path,monkeypatch)
    ah.worker_run(root,None,None,None)
    monkeypatch.setattr(ah,'verify',lambda *args: (p,src,8,np.load(src/'reconstruction.npy'),'bad'))
    monkeypatch.setattr(__import__('experiment_08aj_ah_audit'),'audit',lambda *args:{'pass':False})
    with pytest.raises(ValueError,match='existing AH result'):ah.worker_run(root,None,None,None)

def test_guard_rejects_invalid_budgets(tmp_path,monkeypatch):
    root,_,p=small(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='wall limit'):ah.supervise(root,None,None,None,wall_seconds=0)
    with pytest.raises(ValueError,match='memory cap'):ah.supervise(root,None,None,None,max_mib=1)

def test_worker_source_namespace_locked(tmp_path,monkeypatch):
    root,src,p=small(tmp_path,monkeypatch)
    # The fixture patches verify for numerical tests. Exercise its real
    # source gate via a saved original implementation.
    monkeypatch.setattr(ah,'verify',REAL_VERIFY)
    monkeypatch.setattr(ah,'plan_for',lambda *args:{'different':'plan'})
    with pytest.raises(ValueError):ah.verify(root,None,None,None)

def test_exclusive_initialization(tmp_path,monkeypatch):
    root,_,p=small(tmp_path,monkeypatch)
    with pytest.raises(FileExistsError):ah.init(root,None,None,None,'information_diag','same')

def test_no_prospective_backend_implemented():
    assert ah.SCHEMA.endswith('-v1')
    assert ah.plan_for.__name__=='plan_for'

def test_supervisor_kills_timeout_without_unlocked_execution(tmp_path,monkeypatch):
    root,src,p=small(tmp_path,monkeypatch)
    class Child:
        pid=123456
        returncode=None
        killed=False
        def poll(self):return self.returncode
        def kill(self):self.killed=True;self.returncode=-9
        def communicate(self,timeout=None):return ('','')
    child=Child()
    monkeypatch.setattr(ah.subprocess,'Popen',lambda *a,**kw:child)
    ticks=iter([0.,2.,2.])
    monkeypatch.setattr(ah.time,'monotonic',lambda :next(ticks))
    out=ah.supervise(root,None,None,None,wall_seconds=1)
    assert child.killed
    assert out['verdict']=='AH_ENGINEERING_GUARD_STOP'
    assert out['reason']=='WALL_TIMEOUT'
    assert out['production_execution_allowed'] is False
    assert ah.verify_chain(root,p)[0]==0


def test_atomic_publish_never_overwrites(tmp_path):
    dst=tmp_path/'container';dst.mkdir()
    ah.atomic_dir(dst,'cp_00000001',{'state.npy':b'test','receipt.json':b'{}'})
    with pytest.raises(FileExistsError):
        ah.atomic_dir(dst,'cp_00000001',{'state.npy':b'changed'})
    assert (dst/'cp_00000001'/'state.npy').read_bytes()==b'test'
