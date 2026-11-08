import json
import shutil
from pathlib import Path
import pytest
import experiment_08aj_t as t
import experiment_08aj_t_audit as auditor

CODE=Path(__file__).resolve().parent
REVIEW=CODE/t.REVIEW_FILE

@pytest.fixture
def prepared(tmp_path):
    p=tmp_path/'draft'
    t.prepare(p,CODE,REVIEW)
    return p

def test_candidate_prepared_and_gated(prepared):
    j=json.loads((prepared/'freeze_candidate.json').read_text())
    assert j['planned_jobs']==480
    assert len(j['locks'])==5 and all(g['status']=='BLOCKED' for g in j['locks'])
    assert not j['frozen'] and not j['confirmatory_execution_allowed']

def test_verified(prepared):
    assert t.check(prepared,CODE)['verdict']=='T_CANDIDATE_SOURCE_MATCH'
    assert auditor.audit(prepared,CODE)['pass']

def test_no_overwrite(prepared):
    with pytest.raises(FileExistsError):t.prepare(prepared,CODE,REVIEW)

def test_source_tamper_detected(prepared,tmp_path):
    copy=tmp_path/'source';copy.mkdir()
    for n in t.SOURCES:shutil.copyfile(CODE/n,copy/n)
    (copy/'experiment_08aj_r.py').write_text('tampered')
    with pytest.raises(ValueError):t.check(prepared,copy)
    assert not auditor.audit(prepared,copy)['pass']

def test_candidate_tamper_detected(prepared):
    p=prepared/'freeze_candidate.json';obj=json.loads(p.read_text());obj['frozen']=True;p.write_bytes(t.canonical(obj))
    with pytest.raises(ValueError):t.check(prepared,CODE)
    assert not auditor.audit(prepared,CODE)['pass']

def test_review_tamper_detected(prepared):
    p=prepared/'review_source.json';obj=json.loads(p.read_text());obj['date']='changed';p.write_bytes(t.canonical(obj))
    assert not auditor.audit(prepared,CODE)['pass']

def test_bad_review_status_rejected(tmp_path):
    p=tmp_path/'bad.json';review=json.loads(REVIEW.read_text());review['confirmatory_execution_allowed']=True
    p.write_text(json.dumps(review))
    with pytest.raises(ValueError):t.prepare(tmp_path/'out',CODE,p)

def test_unlock_commands_rejected():
    # No programmatic production entrypoint: only plan/check are implemented.
    import inspect
    src=inspect.getsource(t.main)
    assert 'FREEZE_BLOCKED' in src and "('freeze','execute','unlock')" in src
