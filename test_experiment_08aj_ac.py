from pathlib import Path
import json
import pytest
import experiment_08aj_ac as ac
import experiment_08aj_ac_audit as audit

def test_gates_are_blocked():
    assert len(ac.GAPS)==5
    assert ac.CEILINGS['status']=='PROPOSED_NOT_APPROVED'
    assert ac.CEILINGS['max_retries']==0

def test_manifest_has_no_unlock(monkeypatch):
    monkeypatch.setattr(ac,'validate_locks',lambda *args:{'aa_manifest_sha256':'test'})
    monkeypatch.setattr(ac,'snapshot',lambda root:{'information_diag__same':{'receipt.json':'sha'}})
    monkeypatch.setattr(ac,'filehash',lambda f:'hash')
    c=ac.candidate(*([Path('any')]*6))
    assert c['production_480_job_executor_implemented'] is False
    assert c['confirmatory_execution_allowed'] is False
    assert c['frozen'] is False
    assert c['mid_job_resume_implemented'] is False

def test_atomic_prepare_and_check(monkeypatch,tmp_path):
    c={'schema':ac.SCHEMA,'remaining_gates':[],'confirmatory_execution_allowed':False,'numerical_jobs_attested_not_yet_replayed':1}
    monkeypatch.setattr(ac,'candidate',lambda *args:c)
    root=tmp_path/'candidate'
    r=ac.prepare(root,*([Path('x')]*6))
    assert r['verdict']=='AC_READINESS_CANDIDATE_PREPARED'
    assert ac.check(root,*([Path('x')]*6))['verdict']=='AC_SOURCE_AND_BLOCKER_GATE_MATCH'
    with pytest.raises(FileExistsError):ac.prepare(root,*([Path('x')]*6))

def test_changed_candidate_rejected(monkeypatch,tmp_path):
    base={'schema':ac.SCHEMA,'frozen':False,'numerical_jobs_attested_not_yet_replayed':1}
    monkeypatch.setattr(ac,'candidate',lambda *args:base)
    p=tmp_path/'ac';ac.prepare(p,*([Path('x')]*6))
    (p/'ac_candidate.json').write_text(json.dumps({'schema':ac.SCHEMA,'frozen':True})+'\n')
    with pytest.raises(ValueError):ac.check(p,*([Path('x')]*6))

def test_unexpected_staging_refused(tmp_path):
    p=tmp_path/'jobs';p.mkdir();(p/'.staging__information_diag__same').mkdir()
    with pytest.raises(ValueError,match='unfinished'):ac.snapshot(tmp_path)

def test_incomplete_reconstruction_refused(tmp_path):
    p=tmp_path/'jobs'/'information_diag__same';p.mkdir(parents=True)
    (p/'receipt.json').write_text('{}')
    with pytest.raises(ValueError,match='incomplete'):ac.snapshot(tmp_path)

def test_unsafe_resource_relaxation_rejected():
    with pytest.raises(ValueError,match='cannot relax'):
        ac.guarded_run('a','a','a','information_diag','same','a',wall_seconds=601)
    with pytest.raises(ValueError,match='cannot relax'):
        ac.guarded_run('a','a','a','information_diag','same','a',rss_bytes=9*1024**3)

def test_unauthorized_policy_rejected():
    with pytest.raises(ValueError):ac.ab.job_id('production','same')

def test_audit_indicates_not_ready(monkeypatch,tmp_path):
    c={'engineering_evidence_sha256':{'n8':{'information_diag__same':{}},'n32':{'information_diag__same':{}}},
       'remaining_gates':[{'gate':i,'title':title,'status':s} for i,title,s in ac.GAPS],
       'scientific_signoff':False,'resource_policy_approved':False,'frozen':False,
       'confirmatory_execution_allowed':False,'production_480_job_executor_implemented':False,
       'mid_job_resume_implemented':False,'hard_os_memory_limit_implemented':False,
       'readiness_verdict':'AC_NOT_READY_FOR_CONFIRMATORY_EXECUTION'}
    monkeypatch.setattr(ac,'check',lambda *args:{'verdict':'AC_SOURCE_AND_BLOCKER_GATE_MATCH'})
    monkeypatch.setattr(ac,'load_canonical',lambda *args:c)
    monkeypatch.setattr(audit,'audit_ab',lambda *args:{'pass':True,'audited_engineering_jobs':1,
             'details':[{'job_id':'information_diag__same'}],'errors':[]})
    result=audit.audit(*([tmp_path]*7))
    assert result['pass'] and not result['production_480_job_certified']

def test_audit_rejects_failed_numerics(monkeypatch,tmp_path):
    c={'engineering_evidence_sha256':{'n8':{},'n32':{}},'remaining_gates':[],
       'readiness_verdict':'AC_NOT_READY_FOR_CONFIRMATORY_EXECUTION'}
    monkeypatch.setattr(ac,'check',lambda *args:{})
    monkeypatch.setattr(ac,'load_canonical',lambda *args:c)
    monkeypatch.setattr(audit,'audit_ab',lambda *args:{'pass':False,'audited_engineering_jobs':0,'details':[],'errors':['wrong RMSE']})
    assert not audit.audit(*([tmp_path]*7))['pass']
