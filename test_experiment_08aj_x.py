import json
import shutil
import pytest
from pathlib import Path
from experiment_08aj_x import DEPENDENCIES,prepare,check,canonical
from experiment_08aj_x_audit import audit

def fixture(tmp):
    src=tmp/'src';src.mkdir()
    for name in DEPENDENCIES:(src/name).write_text('test source '+name)
    out=tmp/'output'
    return src,out

def test_prepare(tmp_path):
    src,out=fixture(tmp_path)
    status=prepare(out,src)
    assert status['decisions_pending']==7 and not status['frozen']

def test_check(tmp_path):
    src,out=fixture(tmp_path);prepare(out,src)
    assert check(out,src)['verdict']=='X_ESTIMAND_SOURCE_MATCH'

def test_auditor(tmp_path):
    src,out=fixture(tmp_path);prepare(out,src)
    assert audit(out,src)['pass']

def test_overwrite_refused(tmp_path):
    src,out=fixture(tmp_path);prepare(out,src)
    with pytest.raises(FileExistsError):prepare(out,src)

def test_changed_source(tmp_path):
    src,out=fixture(tmp_path);prepare(out,src)
    (src/DEPENDENCIES[0]).write_text('changed')
    with pytest.raises(ValueError):check(out,src)
    assert not audit(out,src)['pass']

def test_review_tamper(tmp_path):
    src,out=fixture(tmp_path);prepare(out,src)
    review=json.loads((out/'estimand_review.json').read_bytes());review['gain_definition']['condition']='wrong'
    (out/'estimand_review.json').write_bytes(canonical(review))
    assert not audit(out,src)['pass']

def test_unlock_tamper(tmp_path):
    src,out=fixture(tmp_path);prepare(out,src)
    status=json.loads((out/'run_status.json').read_bytes());status['confirmatory_execution_allowed']=True
    (out/'run_status.json').write_bytes(canonical(status))
    assert not audit(out,src)['pass']

def test_no_ci_for_fixed_cohort(tmp_path):
    src,out=fixture(tmp_path);prepare(out,src)
    review=json.loads((out/'estimand_review.json').read_text())
    assert 'no sampling confidence interval' in review['targets']['fixed_cohort']['uncertainty']
    assert 'conditional' in review['analysis']['inference_recommendation']
