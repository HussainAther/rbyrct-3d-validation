from pathlib import Path
import json
import pytest
import experiment_08aj_m as m
import experiment_08aj_z as z
from experiment_08aj_z_audit import audit

@pytest.fixture
def fixture(tmp_path):
    md=tmp_path/'m';m.prepare(md)
    root=tmp_path/'z';z.prepare(root,md,n=8)
    return root,md

def test_contract_stays_disabled(fixture):
    root,md=fixture;p,_=z.check(root,md)
    assert p['m_job_count']==480 and p['confirmatory_execution_allowed'] is False
    assert p['resource_failure_policy']['approval']=='PROPOSED_NOT_APPROVED'

def test_refuse_overwrite(fixture):
    root,md=fixture
    with pytest.raises(FileExistsError):z.prepare(root,md)

def test_one_numerical_job_and_independent_rmse(fixture):
    root,md=fixture
    out=z.run(root,md,'information_diag','same')
    assert out['new_jobs']==['information_diag__same']
    assert audit(root,md)['pass']
    assert z.run(root,md,'information_diag','same')['reused_jobs']==['information_diag__same']

def test_tampered_diagnostics_fail(fixture):
    root,md=fixture;z.run(root,md,'coverage','independent')
    file=root/'diagnostics'/'coverage__independent.json'
    d=json.loads(file.read_text());d['rmse']+=1;file.write_bytes(z.canonical(d))
    assert not audit(root,md)['pass']

def test_source_mismatch(fixture):
    root,md=fixture;file=root/'z_plan.json';d=json.loads(file.read_text());d['frozen']=True
    file.write_bytes(z.canonical(d))
    with pytest.raises(ValueError):z.check(root,md)
    assert not audit(root,md)['pass']

def test_denied_production(fixture):
    root,md=fixture
    with pytest.raises(ValueError):z.run(root,md,'information_diag','unknown')
    assert z.check(root,md)[0]['confirmatory_execution_allowed'] is False

def test_completeness_requires_ten(fixture):
    root,md=fixture;z.run(root,md,'information_diag','same')
    assert not audit(root,md,require_complete=True)['pass']

def test_failures_preserved_and_not_silently_retried(fixture):
    root,md=fixture
    z.write_failure(root,'information_diag__same','SIMULATED','test fault')
    with pytest.raises(ValueError,match='prior failure'):z.run(root,md,'information_diag','same')
    assert not audit(root,md)['pass']
