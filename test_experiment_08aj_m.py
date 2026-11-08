"""08AJ-M outcome-free protocol contract regression tests."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from experiment_08aj_m import SOURCE_FILES, prepare,check,roster,canonical,attach_engineering,proposed_contract
from experiment_08aj_m_audit import audit

@pytest.fixture
def dummy_code(tmp_path):
    code=tmp_path/'code';code.mkdir()
    for name in SOURCE_FILES:(code/name).write_text('fixture '+name+'\n')
    return code

def test_480_unique_locked_jobs():
    js=roster()
    assert len(js)==480 and len({j['job_id'] for j in js})==480
    assert all(j['execution_allowed'] is False and j['mart_epochs']==16 for j in js)

def test_prepare_check_and_audit(tmp_path,dummy_code):
    root=tmp_path/'result';status=prepare(root,code_root=dummy_code)
    assert status['planned_jobs']==480
    check(root,code_root=dummy_code)
    assert audit(root,code_root=dummy_code)['pass']

def test_refuses_overwrite(tmp_path,dummy_code):
    root=tmp_path/'result';prepare(root,code_root=dummy_code)
    with pytest.raises(FileExistsError):prepare(root,code_root=dummy_code)

def test_detects_roster_tampering(tmp_path,dummy_code):
    root=tmp_path/'result';prepare(root,code_root=dummy_code)
    jobs=json.loads((root/'jobs.json').read_bytes());jobs[0]['execution_allowed']=True
    (root/'jobs.json').write_bytes(canonical(jobs))
    assert not audit(root,code_root=dummy_code)['pass']
    with pytest.raises(ValueError):check(root,code_root=dummy_code)

def test_detects_source_change(tmp_path,dummy_code):
    root=tmp_path/'result';prepare(root,code_root=dummy_code)
    (dummy_code/'experiment_04b.py').write_text('changed')
    assert not audit(root,code_root=dummy_code)['pass']
    with pytest.raises(ValueError):check(root,code_root=dummy_code)

def test_detects_contract_gate_change(tmp_path,dummy_code):
    root=tmp_path/'result';prepare(root,code_root=dummy_code)
    p=root/'production_contract_draft.json';doc=json.loads(p.read_bytes())
    doc['execution_gate']['enabled']=True;p.write_bytes(canonical(doc))
    assert not audit(root,code_root=dummy_code)['pass']

def test_require_link_rejects_missing(tmp_path,dummy_code):
    root=tmp_path/'result';prepare(root,code_root=dummy_code)
    assert not audit(root,code_root=dummy_code,require_link=True)['pass']

def test_staging_and_unexpected_root_rejected(tmp_path,dummy_code):
    root=tmp_path/'result';prepare(root,code_root=dummy_code)
    (root/'unexpected.txt').write_text('not allowed')
    assert not audit(root,code_root=dummy_code)['pass']

def test_draft_explicitly_not_certified():
    c=proposed_contract()
    assert c['execution_gate']['enabled'] is False
    assert c['execution_gate']['full_16_epoch_production_numerical_replay_certified'] is False
    assert c['frozen'] is False

def test_engineering_attachment_reuses_identical_evidence(tmp_path,dummy_code,monkeypatch):
    from experiment_08aj_m import REQUIRED_JOB_ARRAYS
    import experiment_08aj_l_audit
    root=tmp_path/'M';prepare(root,code_root=dummy_code)
    l=tmp_path/'L';(l/'engineering_jobs').mkdir(parents=True)
    (l/'protocol_review_draft.json').write_text('historical engineering protocol\n')
    for model in ('same','independent'):
        d=l/'engineering_jobs'/model;d.mkdir()
        for name in REQUIRED_JOB_ARRAYS:(d/name).write_bytes((name+model).encode())
        (d/'receipt.json').write_text('fixture receipt')
    monkeypatch.setattr(experiment_08aj_l_audit,'audit',lambda path:{'pass':True,'details':[
        {'model':m,'max_abs_replay_error':0.0,'pass':True} for m in ('same','independent')]})
    first=attach_engineering(root,l,code_root=dummy_code)
    assert first['verdict']=='M_ENGINEERING_ATTACHMENT_PASS'
    second=attach_engineering(root,l,code_root=dummy_code)
    assert second['verdict']=='M_ENGINEERING_ATTACHMENT_REUSED'
    (l/'engineering_jobs'/'same'/'order.npy').write_bytes(b'changed')
    with pytest.raises(ValueError):attach_engineering(root,l,code_root=dummy_code)
