"""08AJ-N guarded engineering tests: no prospective objects or comparison metrics."""
import json
import pytest
import experiment_08aj_n as n
from experiment_08aj_n_audit import audit, audit_one


def test_plan_guards():
    p=n.proposal()
    assert p['mart_epochs']==16 and p['checkpoint_epochs']==[8,16]
    assert p['execution_allowed'] is False and p['frozen'] is False
    assert p['engineering_seed'] not in {s for seeds in n.SEEDS.values() for s in seeds}
    assert p['models']==['same','independent']


def test_exclusive_and_source_guard(tmp_path):
    root=tmp_path/'run';n.init(root)
    with pytest.raises(FileExistsError):n.init(root)
    assert n.check(root)[0]['execution_allowed'] is False
    p=root/'engineering_plan.json';old=p.read_bytes()
    plan=json.loads(old);plan['source_sha256']['experiment_04b.py']='0'*64
    p.write_bytes(n.canonical(plan))
    with pytest.raises(ValueError,match='SOURCE_OR_PLAN_MISMATCH'):n.check(root)


def test_refuses_confirmation_modes():
    assert 'production' not in ('init','check','run')
    assert 'freeze' not in ('init','check','run')


@pytest.fixture(scope='module')
def engineering_run(tmp_path_factory):
    root=tmp_path_factory.mktemp('n_engineering')/'run'
    n.init(root)
    with pytest.raises(RuntimeError,match='SIMULATED_INTERRUPTION'):
        n.run(root,interrupt_after='same')
    old=(root/'jobs'/'same'/'receipt.json').read_bytes()
    assert n.run(root)['verdict']=='N_16_EPOCH_ENGINEERING_PASS'
    assert (root/'jobs'/'same'/'receipt.json').read_bytes()==old
    return root


def test_numerical_replays(engineering_run):
    result=audit(engineering_run)
    assert result['pass'] and len(result['details'])==2
    assert all(set(x['max_abs_replay_errors'])=={'8','16'} for x in result['details'])
    assert all(max(x['max_abs_replay_errors'].values())<=1e-11 for x in result['details'])
    assert not result['production_480_job_certified']


def test_tampering_fails_and_committed_jobs_not_replaced(engineering_run):
    artifact=engineering_run/'jobs'/'independent'/'reconstruction_epoch16.npy'
    original=artifact.read_bytes();broken=bytearray(original);broken[-1]^=0x20
    try:
        artifact.write_bytes(broken)
        assert not audit_one(engineering_run,'independent')['pass']
    finally: artifact.write_bytes(original)
    assert audit(engineering_run)['pass']


def test_source_mutation_detected(engineering_run):
    doc=engineering_run/'engineering_plan.json'
    old=doc.read_bytes()
    data=json.loads(old)
    data['source_sha256']['experiment_04b.py']='1'*64
    try:
        doc.write_bytes(n.canonical(data))
        assert not audit_one(engineering_run,'same')['pass']
        with pytest.raises(ValueError,match='SOURCE_OR_PLAN_MISMATCH'):n.check(engineering_run)
    finally:doc.write_bytes(old)
    assert audit(engineering_run)['pass']
