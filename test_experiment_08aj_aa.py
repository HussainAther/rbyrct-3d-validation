import json
import pytest
import experiment_08aj_m as m
import experiment_08aj_aa as aa
from experiment_08aj_aa_audit import audit

@pytest.fixture
def setup(tmp_path):
    md=tmp_path/'m';m.prepare(md)
    root=tmp_path/'aa';aa.prepare(root,md)
    return root,md

def test_480_specs_and_96_groups(setup):
    root,md=setup;plan,_,groups=aa.check(root,md)
    assert len(groups)==96 and plan['confirmatory_execution_allowed'] is False
    assert audit(root,md)['pass']

def test_all_five_policies_share_one_noise_group(setup):
    root,md=setup;rows=json.loads((root/'job_specifications.json').read_text())
    key=rows[0]['shared_catalogue_key'];members=[x for x in rows if x['shared_catalogue_key']==key]
    assert len(members)==5 and len({x['policy'] for x in members})==5
    assert all(x['warm_prefix']==64 for x in members if x['policy']!='complete_view')
    assert next(x for x in members if x['policy']=='complete_view')['warm_prefix'] is None

def test_overwrite_refused(setup):
    root,md=setup
    with pytest.raises(FileExistsError):aa.prepare(root,md)

def test_receipt_resume_audit(setup):
    root,md=setup
    first=aa.rehearse(root,md);second=aa.rehearse(root,md)
    assert len(first['new'])==3 and len(second['reused'])==3
    assert audit(root,md,require_rehearsal=True)['pass']

def test_modified_receipt_detected(setup):
    root,md=setup;aa.rehearse(root,md)
    p=root/'rehearsal_receipts'/'contract_check.json';v=json.loads(p.read_text());v['no_confirmatory_outcomes']=False;p.write_bytes(aa.canonical(v))
    with pytest.raises(ValueError):aa.rehearse(root,md)
    assert not audit(root,md)['pass']

def test_mutated_job_rejected(setup):
    root,md=setup;p=root/'job_specifications.json';data=json.loads(p.read_text());data[0]['execution_allowed']=True;p.write_bytes(aa.canonical(data))
    with pytest.raises(ValueError):aa.check(root,md)
    assert not audit(root,md)['pass']

def test_unauthorized_execution_blocked(setup):
    root,md=setup
    with pytest.raises(ValueError):aa.rehearse(root,md,['production_run'])
    assert aa.check(root,md)[0]['production_numerical_certified'] is False

def test_bad_shared_group_fails(setup):
    root,md=setup;p=root/'job_specifications.json';data=json.loads(p.read_text());data[0]['shared_catalogue_key']='wrong';p.write_bytes(aa.canonical(data))
    assert not audit(root,md)['pass']
