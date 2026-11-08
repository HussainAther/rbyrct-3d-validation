"""08AJ-Q fixed noncohort engineering harness tests (no confirmatory runs)."""
from pathlib import Path
import json,shutil
import numpy as np
import pytest
import experiment_08aj_q as q
from experiment_08aj_q_audit import audit, audit_one

@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    d=tmp_path_factory.mktemp('q_real')/'engine'
    q.init(d,8)
    q.run_one(d,'information_diag','same')
    q.run_one(d,'uniform_multiscale','same')
    q.run_one(d,'complete_view','independent')
    return d

def test_study_gate_and_cardinality(prepared):
    p,h=q.check(prepared)
    assert p['execution_allowed'] is False and p['confirmatory_execution_allowed'] is False
    assert p['engineering_seed'] not in {x for group in q.SEEDS.values() for x in group}
    assert p['n']==8 and p['mart_epochs']==2

def test_three_genuine_jobs_audited(prepared):
    result=audit(prepared)
    assert result['pass'] and result['audited_jobs']==3
    assert all(x['max_abs_replay_error']<=1e-11 for x in result['details'])

def test_noise_paired_same_model_across_policies(prepared):
    a=prepared/'jobs'/'information_diag__same'
    b=prepared/'jobs'/'uniform_multiscale__same'
    assert np.array_equal(np.load(a/'noisy_catalogue.npy'),np.load(b/'noisy_catalogue.npy'))
    assert not np.array_equal(np.load(a/'order.npy'),np.load(b/'order.npy'))

def test_committed_reuse_no_overwrite(prepared):
    f=prepared/'jobs'/'information_diag__same'/'receipt.json';before=f.read_bytes()
    result=q.run_one(prepared,'information_diag','same')
    assert result['verdict']=='Q_ENGINEERING_JOB_REUSED' and f.read_bytes()==before

def test_invalid_policy_and_source_integrity(prepared,tmp_path):
    with pytest.raises(ValueError,match='unauthorized'):
        q.run_one(prepared,'fictional_policy','same')
    changed=tmp_path/'changed';shutil.copytree(prepared,changed)
    p=changed/'engineering_plan.json';obj=json.loads(p.read_text())
    obj['mart_epochs']=999;p.write_bytes(q.canonical(obj))
    with pytest.raises(ValueError,match='MISMATCH'):q.check(changed)

def test_artifact_corruption_detected(prepared,tmp_path):
    changed=tmp_path/'corrupt';shutil.copytree(prepared,changed)
    f=changed/'jobs'/'information_diag__same'/'reconstruction.npy'
    with f.open('ab') as fh:fh.write(b'attack')
    assert not audit_one(changed,'information_diag','same')['pass']
    assert not audit(changed)['pass']
    with pytest.raises(ValueError,match='rejected'):
        q.run_one(changed,'information_diag','same')

def test_recovery_after_committed_interruption(tmp_path):
    root=tmp_path/'recovery';q.init(root,8)
    with pytest.raises(RuntimeError,match='SIMULATED_INTERRUPTION'):
        q.run_one(root,'coverage','independent',interrupt_after_commit=True)
    assert audit_one(root,'coverage','independent')['pass']
    assert q.run_one(root,'coverage','independent')['verdict']=='Q_ENGINEERING_JOB_REUSED'

def test_no_overwrite_and_unexpected_job(prepared):
    with pytest.raises(FileExistsError):q.init(prepared,8)
    foreign=prepared/'jobs'/'prospective_cohort';foreign.mkdir()
    try:
        with pytest.raises(ValueError,match='unexpected'):q.check(prepared)
    finally:
        foreign.rmdir()
