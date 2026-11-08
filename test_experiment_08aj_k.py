"""Engineering-only 08AJ-K numerical checkpoint and independent replay tests."""
import json
import pytest
import experiment_08aj_k as k
from experiment_08aj_k_audit import audit_all, audit_one


def test_fixed_engineering_fixture_rejects_production(tmp_path):
    root=tmp_path/'trial';p=k.prepare(root)
    assert p['object_seed']==970099 and not p['execution_allowed']
    assert k.check_plan(root)[0]['engineering_only']
    with pytest.raises(FileExistsError): k.prepare(root)


def test_both_models_replay_exactly(tmp_path):
    root=tmp_path/'trial';k.prepare(root);k.execute(root)
    a=audit_all(root)
    assert a['pass'] and a['replayed_models']==2
    assert all(x['max_abs_replay_error']<=1e-11 for x in a['details'])
    assert not a['production_validation_certified']


def test_resume_preserves_committed_bytes(tmp_path):
    root=tmp_path/'trial';k.prepare(root)
    with pytest.raises(RuntimeError,match='SIMULATED_INTERRUPTION'):
        k.execute(root,stop_after='same')
    before={(root/'jobs'/'same'/p).read_bytes() for p in ('receipt.json','reconstruction.npy')}
    k.execute(root)
    after={(root/'jobs'/'same'/p).read_bytes() for p in ('receipt.json','reconstruction.npy')}
    assert before==after and audit_all(root)['pass']


def test_uncommitted_staging_is_recreated(tmp_path):
    root=tmp_path/'trial';k.prepare(root)
    stage=root/'jobs'/'.same.staging';stage.mkdir()
    (stage/'partial.bin').write_bytes(b'interrupted')
    k.execute(root)
    assert not stage.exists() and audit_all(root)['pass']


def test_corrupted_npy_detected_and_refused(tmp_path):
    root=tmp_path/'trial';k.prepare(root);k.execute(root)
    p=root/'jobs'/'same'/'reconstruction.npy'
    data=bytearray(p.read_bytes());data[-1]^=0x42;p.write_bytes(data)
    assert not audit_one(root,'same')['pass']
    with pytest.raises(ValueError,match='checkpoint invalid'):
        k.execute(root)


def test_receipt_tamper_detected(tmp_path):
    root=tmp_path/'trial';k.prepare(root);k.execute(root)
    p=root/'jobs'/'independent'/'receipt.json'
    receipt=json.loads(p.read_bytes());receipt['model']='same';p.write_text(json.dumps(receipt))
    assert not audit_all(root)['pass']


def test_source_lock_detects_changed_source_digest(tmp_path):
    root=tmp_path/'trial';k.prepare(root)
    plan=json.loads((root/'engineering_plan.json').read_bytes())
    plan['source_sha256']['experiment_04b.py']='0'*64
    (root/'engineering_plan.json').write_bytes(k.canonical(plan))
    with pytest.raises(ValueError,match='SOURCE_MISMATCH'):
        k.check_plan(root)
    assert not audit_one(root,'same')['pass']


def test_extra_job_detected(tmp_path):
    root=tmp_path/'trial';k.prepare(root);k.execute(root)
    (root/'jobs'/'unexpected').mkdir()
    assert not audit_all(root)['pass']
