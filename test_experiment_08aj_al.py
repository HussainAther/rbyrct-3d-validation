"""08AJ-AL fixed engineering-object controls (fast tests; Windows numerics separate)."""
from pathlib import Path
import numpy as np
import pytest
import experiment_08aj_al as al

def test_fixed_objects_distinct():
    assert len(al.OBJECTS)==2 and len({x['seed'] for x in al.OBJECTS.values()})==2
    assert al.af.SEED not in {x['seed'] for x in al.OBJECTS.values()}

def test_only_two_object_identifiers():
    with pytest.raises(ValueError):al.group_name('object_00','same')

def test_only_two_models():
    with pytest.raises(ValueError):al.group_name('engineering_alpha','unexpected')

def test_only_two_primary_policies():
    with pytest.raises(ValueError):al.job_name('engineering_alpha','same','complete_view')

def test_distinct_job_names():
    ids={al.job_name(o,m,p) for o in al.OBJECTS for m in al.MODELS for p in al.POLICIES}
    assert len(ids)==8

def test_canonical_receipts(tmp_path):
    d=tmp_path/'receipt.json';al.write(d,{'z':1,'a':2})
    assert d.read_bytes()==b'{"a":2,"z":1}\n'
    assert al.read(d)=={'a':2,'z':1}

def test_noncanonical_receipt_rejected(tmp_path):
    d=tmp_path/'receipt.json';d.write_text('{"z": 1}')
    with pytest.raises(ValueError,match='noncanonical'):al.read(d)

def test_deterministic_array_serializer():
    x=np.array([.1,.2],dtype=np.float64)
    assert al.array_bytes(x)==al.array_bytes(x)

def test_atomic_commit_rejects_overwrite(tmp_path):
    d=tmp_path/'job';(d/'checkpoints').mkdir(parents=True)
    s={'job_id':'engineering_alpha__same__information_diag'}
    al.write(d/'source.json',{'namespace':'MULTI_OBJECT_ENGINEERING_ONLY'})
    x=np.full(8**3,.3)
    al.commit(d,s,x,256,'GENESIS')
    with pytest.raises(FileExistsError):al.commit(d,s,x,256,'GENESIS')

def test_checkpoint_chain_rejects_state_tamper(tmp_path):
    d=tmp_path/'job';(d/'checkpoints').mkdir(parents=True)
    s={'job_id':'engineering_alpha__same__information_diag','n':8,'budget':128,'epochs':2}
    al.write(d/'source.json',{'namespace':'MULTI_OBJECT_ENGINEERING_ONLY'})
    al.commit(d,s,np.full(8**3,.3),256,'GENESIS')
    al.verify_chain(d,s)
    (d/'checkpoints'/'cp_00000256'/'state.npy').write_bytes(b'changed')
    with pytest.raises(ValueError,match='checkpoint'):al.verify_chain(d,s)

def test_checkpoint_chain_rejects_other_job(tmp_path):
    d=tmp_path/'job';(d/'checkpoints').mkdir(parents=True)
    al.write(d/'source.json',{'namespace':'MULTI_OBJECT_ENGINEERING_ONLY'})
    one={'job_id':'engineering_alpha__same__information_diag','n':8,'budget':128,'epochs':2}
    two={'job_id':'engineering_beta__same__information_diag','n':8,'budget':128,'epochs':2}
    al.commit(d,one,np.full(8**3,.3),256,'GENESIS')
    with pytest.raises(ValueError,match='checkpoint'):al.verify_chain(d,two)

def test_locked_execution_modes_declared():
    import inspect
    source=inspect.getsource(al.main)
    assert "'production-run','unlock','freeze'" in source
    assert 'PROSPECTIVE_EXECUTION_DISABLED' in source
