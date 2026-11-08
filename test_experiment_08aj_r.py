"""08AJ-R multi-policy engineering invariants, never confirmatory outcomes."""
import json, shutil
import pytest
import numpy as np
import experiment_08aj_r as r
from experiment_08aj_r_audit import audit

@pytest.fixture(scope='module')
def complete(tmp_path_factory):
    root=tmp_path_factory.mktemp('r_full')/'engine'
    r.init(root,8)
    report=r.run(root)
    assert len(report['new_jobs'])==10
    return root

def test_engineering_only_gate_and_count(complete):
    m,_=r.check(complete)
    assert m['number_of_jobs']==10 and not m['confirmatory_execution_allowed']
    assert not m['frozen'] and m['engineering_seed']==970099
    assert m['epochs']==2

def test_complete_independent_numerical_replay(complete):
    result=audit(complete,require_complete=True)
    assert result['pass'],result['errors']
    assert result['audited_jobs']==10 and result['max_abs_replay_error']<=1e-11
    assert all(x['jobs_present']==5 and x['shared_catalogue_verified'] for x in result['cross_policy'].values())

def test_job_reuse_does_not_overwrite(complete):
    path=complete/'q_jobs'/'jobs'/'coverage__same'/'receipt.json'
    before=path.read_bytes()
    result=r.run(complete,'coverage','same')
    assert result['reused_jobs']==['coverage__same'] and not result['new_jobs']
    assert path.read_bytes()==before

def test_tampered_numerical_data_detected(complete,tmp_path):
    clone=tmp_path/'tamper';shutil.copytree(complete,clone)
    artifact=clone/'q_jobs'/'jobs'/'uniform_multiscale__same'/'measurements.npy'
    with artifact.open('ab') as f:f.write(b'tamper')
    result=audit(clone,require_complete=True)
    assert not result['pass'] and any('replay failed' in x for x in result['errors'])

def test_incomplete_jobs_distinct_from_invalid(complete,tmp_path):
    clone=tmp_path/'partial';shutil.copytree(complete,clone)
    shutil.rmtree(clone/'q_jobs'/'jobs'/'complete_view__same')
    assert audit(clone,require_complete=False)['pass']
    assert not audit(clone,require_complete=True)['pass']

def test_forbidden_production_and_plan_changes(complete,tmp_path):
    with pytest.raises(ValueError,match='unauthorized'):r.run(complete,'made_up','same')
    with pytest.raises(FileExistsError):r.init(complete,8)
    clone=tmp_path/'bad';shutil.copytree(complete,clone)
    p=clone/'multi_job_plan.json';m=json.loads(p.read_bytes())
    m['confirmatory_execution_allowed']=True;p.write_bytes(r.canonical(m))
    with pytest.raises(ValueError,match='MISMATCH'):r.check(clone)
    assert not audit(clone)['pass']

def test_cross_model_distinct_catalogues(complete):
    jobs=complete/'q_jobs'/'jobs'
    same=np.load(jobs/'coverage__same'/'noisy_catalogue.npy')
    independent=np.load(jobs/'coverage__independent'/'noisy_catalogue.npy')
    assert not np.array_equal(same,independent)

def test_symlink_or_uncommitted_staging_rejected(complete,tmp_path):
    clone=tmp_path/'staging';shutil.copytree(complete,clone)
    (clone/'q_jobs'/'jobs'/'.staging__coverage__same').mkdir()
    assert not audit(clone)['pass']
