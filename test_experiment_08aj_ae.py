"""AE noncohort dispatcher security, recovery, and independent-audit tests."""
import json
from pathlib import Path
import pytest
import experiment_08aj_ae as ae
import experiment_08aj_ae_audit as auditor

def fake_environment(tmp_path,monkeypatch):
    root=tmp_path/'ae'; aa=tmp_path/'aa';m=tmp_path/'m';ab=tmp_path/'ab'
    for x in (aa,m,ab):x.mkdir()
    p={'schema':ae.SCHEMA,'engineering_seed':ae.ad.SEED,'n':8,
       'policy_model_templates':{p+'__'+mm:48 for p in ae.aa.POLICIES for mm in ae.aa.MODELS},
       'production_jobs_executed':0,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    monkeypatch.setattr(ae,'context',lambda *args:p)
    return root,aa,m,ab,p

def fake_dispatch(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_environment(tmp_path,monkeypatch)
    def validate(*args):return None
    def initialize(numerical,*args):
        numerical.mkdir();(numerical/'checkpoints').mkdir()
        ae.store(numerical/'plan.json',{'n':2,'budget':2,'epochs':2,'production_execution_allowed':False})
        return {}
    monkeypatch.setattr(ae.ad,'validate_ab',validate)
    monkeypatch.setattr(ae.ad,'initialize',initialize)
    ae.init(root,aa,m,ab)
    return root,aa,m,ab,p

def test_init_locked_and_immutable(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_environment(tmp_path,monkeypatch)
    assert ae.init(root,aa,m,ab)['aa_production_specs']==480
    with pytest.raises(FileExistsError):ae.init(root,aa,m,ab)
    assert ae.check(root,aa,m,ab)['production_execution_allowed'] is False

def test_dispatch_matches_only_allowed_template(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    r=ae.dispatch(root,aa,m,ab,'information_diag','same')
    assert r['verdict']=='AE_ENGINEERING_TEMPLATE_DISPATCHED'
    assert ae.receipt(root/'jobs'/'information_diag__same'/'dispatch.json')['production_job_id'] is None
    assert ae.check(root,aa,m,ab)['n']==8

def test_no_prospective_ids_or_unknown_policy(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    with pytest.raises(ValueError):ae.dispatch(root,aa,m,ab,'localized_defects__100','same')
    assert len(list((root/'jobs').iterdir()))==0

def test_fingerprint_detects_edited_plan(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    path=root/'dispatch_plan.json'
    value=ae.receipt(path);value['production_execution_allowed']=True
    path.write_bytes(ae.canonical(value))
    with pytest.raises(ValueError,match='drift'):ae.check(root,aa,m,ab)

def test_dispatch_tamper_rejected(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    ae.dispatch(root,aa,m,ab,'coverage','independent')
    path=root/'jobs'/'coverage__independent'/'dispatch.json'
    value=ae.receipt(path);value['aa_template_count']=49
    path.write_bytes(ae.canonical(value))
    with pytest.raises(ValueError,match='dispatch receipt mismatch'):ae.check(root,aa,m,ab)

def test_checkpoint_plan_tamper_rejected(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    ae.dispatch(root,aa,m,ab,'coverage','same')
    path=root/'jobs'/'coverage__same'/'numerical'/'plan.json'
    path.write_bytes(path.read_bytes()+b'corrupt')
    with pytest.raises(ValueError):ae.check(root,aa,m,ab)

def test_orphan_job_fail_closed(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    (root/'jobs'/'information_diag__same').mkdir()
    with pytest.raises(ValueError,match='missing AE dispatch receipt'):ae.check(root,aa,m,ab)

def test_engineering_run_is_delegated(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    ae.dispatch(root,aa,m,ab,'information_diag','same')
    called=[]
    def fake_run(*args):
        called.append(args);return {'verdict':'AD_ENGINEERING_INTERRUPTED_AT_CHECKPOINT','rows_done':3}
    monkeypatch.setattr(ae.ad,'run',fake_run)
    r=ae.execute(root,aa,m,ab,'information_diag','same',3,600)
    assert r['verdict']=='AE_ENGINEERING_EXECUTION_PAUSED' and r['production_jobs_executed']==0
    assert called[0][4]==3

def test_dispatch_source_drift_rejected(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    p2=dict(p);p2['n']=32
    monkeypatch.setattr(ae,'context',lambda *args:p2)
    with pytest.raises(ValueError,match='drift'):ae.check(root,aa,m,ab)

def test_independent_audit_empty_and_pending(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    ae.dispatch(root,aa,m,ab,'uniform_multiscale','same')
    monkeypatch.setattr(ae.ad,'verify_chain',lambda *args:(3,None,'abc'))
    result=auditor.audit(root,aa,m,ab)
    assert result['pass'] and len(result['pending_engineering_jobs'])==1
    result=auditor.audit(root,aa,m,ab,require_complete=True)
    assert not result['pass']

def test_independent_audit_rejects_changed_evidence(tmp_path,monkeypatch):
    root,aa,m,ab,p=fake_dispatch(tmp_path,monkeypatch)
    ae.dispatch(root,aa,m,ab,'uniform_multiscale','same')
    (root/'jobs'/'uniform_multiscale__same'/'dispatch.json').write_bytes(b'{}')
    assert auditor.audit(root,aa,m,ab)['pass'] is False
