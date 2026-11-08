import json,subprocess,sys
from pathlib import Path
import pytest
import experiment_08aj_aj as aj
import experiment_08aj_aj_audit as auditor


def write_fixture(path, value):
    """Write a valid AD/AH canonical receipt; test the intended failure gate."""
    Path(path).write_bytes(aj.canonical(value))


def test_canonical_deterministic():
    assert aj.canonical({'b':2,'a':1})==aj.canonical({'a':1,'b':2})

def test_plan_requires_valid_policy():
    with pytest.raises(ValueError):aj.plan(None,None,None,'prospective','same')

def test_init_refuses_duplicate(tmp_path,monkeypatch):
    fake={'schema':aj.SCHEMA,'namespace':'LIVE_ENGINEERING_FAULT_TEST_ONLY','policy':'information_diag','model':'same'}
    monkeypatch.setattr(aj,'plan',lambda *args:fake)
    monkeypatch.setattr(aj.ah,'init',lambda root,*args: (Path(root).mkdir(),write_fixture(Path(root)/'plan.json',{'source':{'n':8}})))
    root=tmp_path/'aj'
    assert aj.init(root,None,None,None,'information_diag','same')['verdict']=='AJ_LIVE_ENGINEERING_GATE_PREPARED'
    with pytest.raises(FileExistsError):aj.init(root,None,None,None,'information_diag','same')

def test_check_rejects_invalid_namespace(tmp_path):
    root=tmp_path; write_fixture(root/'plan.json',{'schema':aj.SCHEMA,'namespace':'PRODUCTION'})
    with pytest.raises(ValueError,match='namespace'):aj.check(root,None,None,None)

def test_kill_requires_fresh_chain(tmp_path,monkeypatch):
    monkeypatch.setattr(aj,'check',lambda *args: ({},128,'HASH'))
    with pytest.raises(ValueError,match='before any MART'):aj.inject(tmp_path,None,None,None)

def test_kill_rejects_invalid_target(tmp_path,monkeypatch):
    monkeypatch.setattr(aj,'check',lambda *args: ({},0,'GENESIS'))
    worker=tmp_path/'worker';worker.mkdir()
    write_fixture(worker/'plan.json',{'source':{'budget':128,'epochs':2}})
    with pytest.raises(ValueError,match='target'):aj.inject(tmp_path,None,None,None,target_rows=257)

def test_resume_requires_fault(tmp_path,monkeypatch):
    monkeypatch.setattr(aj,'check',lambda *args: ({},0,'GENESIS'))
    with pytest.raises(ValueError,match='fault receipt'):aj.resume(tmp_path,None,None,None)

def test_worker_rejects_bad_hold():
    script=Path(aj.__file__).with_name(aj.WORKER)
    r=subprocess.run([sys.executable,str(script),'--worker-dir','x','--af-dir','x','--aa-dir','x','--m-dir','x','--post-commit-hold','0'],capture_output=True,text=True)
    assert r.returncode!=0 and 'invalid post-commit hold' in r.stderr

def test_production_mode_blocked():
    r=subprocess.run([sys.executable,aj.__file__,'--mode','production-run','--output-dir','x','--af-dir','x','--aa-dir','x','--m-dir','x'],capture_output=True,text=True)
    assert r.returncode!=0 and 'PRODUCTION_EXECUTION_DISABLED' in r.stderr

def test_independent_audit_fails_without_evidence(tmp_path):
    r=auditor.audit(tmp_path,None,None,None)
    assert r['pass'] is False and r['production_execution_allowed'] is False

def test_fault_receipts_immutable(tmp_path,monkeypatch):
    monkeypatch.setattr(aj,'check',lambda *args: ({},0,'GENESIS'))
    (tmp_path/'fault.json').write_text('{}')
    with pytest.raises(FileExistsError):aj.inject(tmp_path,None,None,None)

def test_write_once(tmp_path):
    path=tmp_path/'receipt.json';aj.write_once(path,{'a':1})
    assert json.loads(path.read_text())=={'a':1}
    with pytest.raises(FileExistsError):aj.write_once(path,{'a':2})

def test_check_rejects_source_drift(tmp_path,monkeypatch):
    root=tmp_path
    data={'schema':aj.SCHEMA,'namespace':'LIVE_ENGINEERING_FAULT_TEST_ONLY','policy':'information_diag','model':'same'}
    write_fixture(root/'plan.json',data)
    monkeypatch.setattr(aj,'plan',lambda *args:{**data,'source_sha256':'different'})
    with pytest.raises(ValueError,match='drift'):aj.check(root,None,None,None)

def test_injection_rejects_invalid_wall_limit(tmp_path,monkeypatch):
    monkeypatch.setattr(aj,'check',lambda *args: ({},0,'GENESIS'))
    (tmp_path/'worker').mkdir()
    write_fixture(tmp_path/'worker'/'plan.json',{'source':{'budget':2048,'epochs':16}})
    with pytest.raises(ValueError,match='deadline'):aj.inject(tmp_path,None,None,None,wall_seconds=0.1)

def test_independent_auditor_maintains_closed_gate(tmp_path):
    result=auditor.audit(tmp_path,None,None,None)
    assert result['production_480_job_certified'] is False
    assert result['resource_policy_approved'] is False
    assert result['no_confirmatory_outcomes'] is True
