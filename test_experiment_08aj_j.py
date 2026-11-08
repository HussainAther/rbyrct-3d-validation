"""Outcome-free validation rehearsal and tampering regression tests."""
import json
import pytest
import experiment_08aj_j as j
from experiment_08aj_j_audit import audit_demo


def test_roster():
    rows=j.jobs()
    assert len(rows)==480
    assert len({x['job_id'] for x in rows})==480
    assert all(not x['execution_allowed'] and x['status']=='PLANNED_ONLY' for x in rows)
    assert len({(x['family'],x['object_seed']) for x in rows})==24


def test_create_plan_source_lock(tmp_path):
    root=tmp_path/'run';j.create_plan(root)
    plan,sha=j.load_plan(root)
    assert sha==j.digest((root/'plan.json').read_bytes())
    assert not plan['frozen'] and not plan['execution_allowed']
    with pytest.raises(FileExistsError): j.create_plan(root)


def test_demo_recovery_idempotent(tmp_path):
    root=tmp_path/'run';j.create_plan(root)
    assert j.demo_recovery(root)['verdict']=='RECOVERY_FIXTURE_PASS'
    before={x.name:x.read_bytes() for x in (root/'engineering_recovery_fixture'/'receipts').glob('*.json')}
    assert j.demo_recovery(root)['verdict']=='RECOVERY_FIXTURE_PASS'
    after={x.name:x.read_bytes() for x in (root/'engineering_recovery_fixture'/'receipts').glob('*.json')}
    assert before==after
    assert audit_demo(root)['pass']


def test_interrupted_recovery(tmp_path):
    root=tmp_path/'run';j.create_plan(root)
    with pytest.raises(RuntimeError,match='SIMULATED_INTERRUPTION'):
        j.demo_recovery(root,fail_after_claim=True)
    assert not audit_demo(root)['pass']
    assert j.demo_recovery(root)['verdict']=='RECOVERY_FIXTURE_PASS'
    assert audit_demo(root)['pass']


def test_tamper_receipt_fails_independent_audit(tmp_path):
    root=tmp_path/'run';j.create_plan(root);j.demo_recovery(root)
    target=root/'engineering_recovery_fixture'/'receipts'/'ENGINEERING_DEMO_B.json'
    record=json.loads(target.read_text())
    record['fixture_digest_sha256']='0'*64
    target.write_text(json.dumps(record))
    assert not audit_demo(root)['pass']
    with pytest.raises(ValueError,match='immutable receipt mismatch'):
        j.demo_recovery(root)


def test_tamper_manifest_fails_independent_audit(tmp_path):
    root=tmp_path/'run';j.create_plan(root);j.demo_recovery(root)
    (root/'manifest.sha256').write_text('0'*64+'  plan.json\n')
    assert not audit_demo(root)['pass']


def test_source_lock_rejects_changed_code(tmp_path):
    root=tmp_path/'run';j.create_plan(root)
    copied=tmp_path/'sources';copied.mkdir()
    for filename in j.REQUIRED_SOURCES:
        (copied/filename).write_bytes((j.Path(j.__file__).parent/filename).read_bytes())
    (copied/'experiment_08aj_g.py').write_bytes(b'altered')
    with pytest.raises(ValueError,match='SOURCE_LOCK_MISMATCH'):
        j.load_plan(root,code_root=copied)


def test_missing_or_duplicate_receipt_detection(tmp_path):
    root=tmp_path/'run';j.create_plan(root);j.demo_recovery(root)
    receipts=root/'engineering_recovery_fixture'/'receipts'
    (receipts/'ENGINEERING_DEMO_C.json').unlink()
    assert not audit_demo(root)['pass']
    j.demo_recovery(root)
    (receipts/'FORGED.json').write_text('{}')
    assert not audit_demo(root)['pass']


def test_production_results_prohibited(tmp_path):
    root=tmp_path/'run';j.create_plan(root);j.demo_recovery(root)
    (root/'rmse.csv').write_text('do not use')
    assert not audit_demo(root)['pass']
