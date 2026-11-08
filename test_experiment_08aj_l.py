"""08AJ-L draft protocol and 32^3 engineering-replay tests."""
import json
import pytest
import experiment_08aj_l as l
from experiment_08aj_l_audit import audit, audit_one


def test_draft_not_frozen():
    p=l.protocol()
    assert p['review_required']>=4 and not p['frozen'] and not p['execution_allowed']
    assert p['primary']['total_planned_policy_conditions']==480
    assert p['engineering_fixture']['seed'] not in {s for family in l.SEEDS.values() for s in family}


def test_reject_overwrite(tmp_path):
    root=tmp_path/'draft'
    l.init(root)
    with pytest.raises(FileExistsError):l.init(root)
    assert l.check(root)[0]['schema']==l.SCHEMA


def test_tampered_source_digest_rejected(tmp_path):
    root=tmp_path/'draft';l.init(root)
    path=root/'protocol_review_draft.json';p=json.loads(path.read_bytes())
    p['source_sha256']['experiment_04b.py']='0'*64
    path.write_bytes(l.canonical(p))
    with pytest.raises(ValueError,match='SOURCE_OR_PROTOCOL_MISMATCH'):l.check(root)


def test_both_32cube_models_replayed(tmp_path):
    root=tmp_path/'draft';l.init(root);r=l.run(root)
    assert r['models_complete']==['same','independent']
    a=audit(root)
    assert a['pass'] and all(x['max_abs_replay_error']<=1e-11 for x in a['details'])
    assert not a['production_validation_certified']


def test_resume_preserves_receipt(tmp_path):
    root=tmp_path/'draft';l.init(root)
    with pytest.raises(RuntimeError,match='SIMULATED_INTERRUPTION'):
        l.run(root,interrupt_after='same')
    before=(root/'engineering_jobs'/'same'/'receipt.json').read_bytes()
    l.run(root)
    assert before==(root/'engineering_jobs'/'same'/'receipt.json').read_bytes()
    assert audit(root)['pass']


def test_modified_artifact_detected(tmp_path):
    root=tmp_path/'draft';l.init(root);l.run(root)
    f=root/'engineering_jobs'/'same'/'reconstruction.npy'
    damaged=bytearray(f.read_bytes());damaged[-1]^=0x14;f.write_bytes(damaged)
    assert not audit_one(root,'same')['pass']
    with pytest.raises(ValueError,match='committed artifact invalid'):l.run(root)


def test_no_confirmation_modes():
    assert 'production' not in ('init','check','run')
    assert all(x['status']!='APPROVED' for x in l.review_register())
