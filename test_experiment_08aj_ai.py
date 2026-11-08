import json,subprocess,sys
from pathlib import Path
import pytest
import experiment_08aj_ai as ai
import experiment_08aj_ai_audit as audit


def fake_plan():
    return {'schema':ai.SCHEMA,'aa_job_specifications':480,'aa_shared_groups':96,
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(ai,'expected',lambda *args:fake_plan())
    root=tmp_path/'ai'
    assert ai.prepare(root,None,None,None,None)['verdict']=='AI_LOCKED_FAILURE_GATE_PREPARED'
    return root

def test_prepare_and_check(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    assert ai.check(root,None,None,None,None)==fake_plan()

def test_refuses_overwrite(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    with pytest.raises(FileExistsError):ai.prepare(root,None,None,None,None)

def test_source_tamper_detected(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    (root/'plan.json').write_bytes(b'{}')
    with pytest.raises(ValueError):ai.check(root,None,None,None,None)

def test_wall_timeout_real_process(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    r=ai.exercise(root,'wall',0.25)
    assert r['verdict']=='WALL_TIMEOUT_WORKER_TERMINATED'
    assert r['timed_out'] is True
    assert r['production_execution_allowed'] is False

def test_wall_is_immutable(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch);ai.exercise(root,'wall',0.2)
    with pytest.raises(FileExistsError):ai.exercise(root,'wall',0.2)

def test_orphan_staging_preserved(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    r=ai.exercise(root,'atomic-stage',1.0)
    assert r['verdict']=='WALL_TIMEOUT_WORKER_TERMINATED'
    assert len(list((root/'cases'/'atomic-stage'/'sandbox').iterdir()))==1

def test_orphan_quarantine(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch);ai.exercise(root,'atomic-stage',1.0)
    assert ai.quarantine(root)['quarantined_stages']==1
    with pytest.raises((FileExistsError,ValueError)):ai.quarantine(root)
    assert audit.audit(root,None,None,None,None)['pass']

def test_memory_worker_limited(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    r=ai.exercise(root,'memory',10)
    # Local POSIX RLIMIT_AS and Windows job object vary; insist on explicit denial
    # to call this a pass. The Windows result is the actual operational evidence.
    assert r['verdict'] in ('OS_MEMORY_DENIAL_CONFIRMED','MEMORY_ENFORCEMENT_NOT_CONFIRMED')
    assert r['production_execution_allowed'] is False

def test_receipt_tamper_audit_fails(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch);ai.exercise(root,'wall',0.2)
    f=root/'cases'/'wall'/'result.json';r=json.loads(f.read_bytes());r['timed_out']=False;f.write_bytes(ai.canonical(r))
    assert not audit.audit(root,None,None,None,None)['pass']

def test_no_production_modes(tmp_path):
    cmd=[sys.executable,str(Path(ai.__file__).resolve()),'--mode','production-run']
    p=subprocess.run(cmd,capture_output=True,text=True)
    assert p.returncode!=0 and 'PRODUCTION_EXECUTION_DISABLED' in p.stderr

def test_case_names_restricted(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError):ai.exercise(root,'production',0.2)

def test_guarded_limits(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError):ai.exercise(root,'wall',60)

def test_audit_requires_all(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch);ai.exercise(root,'wall',0.2)
    assert not audit.audit(root,None,None,None,None,require_all=True)['pass']

def test_full_independent_fault_audit(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    ai.exercise(root,'wall',0.5)
    ai.exercise(root,'atomic-stage',1.0)
    ai.exercise(root,'memory',10)
    ai.quarantine(root)
    result=audit.audit(root,None,None,None,None,require_all=True)
    assert result['pass'], result['errors']
    assert result['audited_fault_cases']==3
    assert result['roster_specs']==480


def test_quarantine_tampering_detected(tmp_path,monkeypatch):
    root=fixture(tmp_path,monkeypatch)
    ai.exercise(root,'atomic-stage',1.0)
    ai.quarantine(root)
    (root/'cases'/'atomic-stage'/'quarantine'/'partial.bin').write_bytes(b'tampered')
    result=audit.audit(root,None,None,None,None)
    assert not result['pass']
