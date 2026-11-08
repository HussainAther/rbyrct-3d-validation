import json
from pathlib import Path
import pytest
import experiment_08aj_m as m
import experiment_08aj_aa as aa
import experiment_08aj_ab as ab
import experiment_08aj_ab_audit as auditor

@pytest.fixture
def contract(tmp_path):
    md=tmp_path/'m';ad=tmp_path/'aa'
    m.prepare(md);aa.prepare(ad,md)
    return tmp_path,ad,md

def test_allowed_shadow_plan_and_disabled_contract(contract):
    root,ad,md=contract
    result=ab.init(root/'ab',ad,md)
    assert result['production_execution_allowed'] is False
    p,_=ab.check(root/'ab',ad,md)
    assert p['production_roster_size']==480 and p['production_jobs_executed']==0

def test_cannot_reinit_or_execute_cohort(contract):
    root,ad,md=contract
    ab.init(root/'ab',ad,md)
    with pytest.raises(FileExistsError):ab.init(root/'ab',ad,md)
    with pytest.raises(ValueError):ab.perform(root/'ab',ad,md,'localized_defects','same')
    with pytest.raises(ValueError):ab.perform(root/'ab',ad,md,'information_diag','production')
    with pytest.raises(ValueError):ab.make_plan(24,'x','x')

def test_source_drift_rejected(contract):
    root,ad,md=contract;ab.init(root/'ab',ad,md)
    f=root/'ab'/'ab_plan.json';d=json.loads(f.read_text());d['production_execution_allowed']=True
    f.write_bytes(ab.canonical(d))
    with pytest.raises(ValueError):ab.check(root/'ab',ad,md)

def test_real_job_replay_and_resume(contract):
    root,ad,md=contract;ab.init(root/'ab',ad,md)
    out=ab.perform(root/'ab',ad,md,'information_diag','same')
    assert out['verdict']=='AB_NUMERICAL_ENGINEERING_JOB_PASS'
    audit=auditor.audit(root/'ab',ad,md)
    assert audit['pass'] and audit['audited_engineering_jobs']==1
    assert audit['details'][0]['max_abs_replay_error']<=1e-11
    reused=ab.perform(root/'ab',ad,md,'information_diag','same')
    assert reused['verdict']=='AB_ENGINEERING_JOB_REUSED'

def test_tamper_rejected(contract):
    root,ad,md=contract;ab.init(root/'ab',ad,md)
    ab.perform(root/'ab',ad,md,'coverage','independent')
    f=root/'ab'/'jobs'/'coverage__independent'/'receipt.json'
    d=json.loads(f.read_text());d['rmse']=123.0;f.write_bytes(ab.canonical(d))
    assert not auditor.audit(root/'ab',ad,md)['pass']
    with pytest.raises(ValueError):ab.perform(root/'ab',ad,md,'coverage','independent')

def test_interruption_reuses_committed_job(contract):
    root,ad,md=contract;ab.init(root/'ab',ad,md)
    with pytest.raises(RuntimeError,match='SIMULATED_INTERRUPTION'):
        ab.perform(root/'ab',ad,md,'uniform_multiscale','same',interrupt_after_commit=True)
    assert ab.perform(root/'ab',ad,md,'uniform_multiscale','same')['verdict']=='AB_ENGINEERING_JOB_REUSED'

def test_staging_preserved_and_detected(contract):
    root,ad,md=contract;ab.init(root/'ab',ad,md)
    stage=root/'ab'/'jobs'/'.staging__coverage__same';stage.mkdir();(stage/'diagnostic.txt').write_text('partial')
    assert not auditor.audit(root/'ab',ad,md)['pass']
    with pytest.raises(RuntimeError,match='incomplete staging'):
        ab.perform(root/'ab',ad,md,'coverage','same')
    assert (stage/'diagnostic.txt').read_text()=='partial'

def test_all_ten_needed_only_when_requested(contract):
    root,ad,md=contract;ab.init(root/'ab',ad,md)
    ab.perform(root/'ab',ad,md,'complete_view','same')
    assert auditor.audit(root/'ab',ad,md)['pass']
    assert not auditor.audit(root/'ab',ad,md,True)['pass']


def test_shared_catalogue_and_warm_prefix(contract):
    root,ad,md=contract;ab.init(root/'ab',ad,md)
    for policy in ('information_diag','uniform_multiscale','coverage'):
        ab.perform(root/'ab',ad,md,policy,'same')
    rep=auditor.audit(root/'ab',ad,md)
    assert rep['pass'] and rep['audited_engineering_jobs']==3
