"""08AJ-AS engineering-only contract-binding and independent audit tests.

Uses the existing AR/AN mock numerical fixture; AS never calls a worker.
"""
import json
import shutil
from pathlib import Path

import pytest

from test_experiment_08aj_an import fx as an_fx
from test_experiment_08aj_ar import ctx as ar_ctx
import experiment_08aj_an as an
import experiment_08aj_ar as ar
import experiment_08aj_as as stage
import experiment_08aj_as_audit as auditor


@pytest.fixture
def ready(ar_ctx):
    root, aa_dir, m_dir = ar_ctx
    ar.prepare(root, aa_dir, m_dir, 8)
    names = []
    for obj in ('engineering_alpha', 'engineering_beta'):
        jid = ar.identifier(obj, 'seed_a', 'same', 'information_diag')
        ar.dispatch(root, aa_dir, m_dir, jid, 'catalogue')
        ar.dispatch(root, aa_dir, m_dir, jid, 'dispatch')
        names.append(jid)
    return root, aa_dir, m_dir, names


def prepared(ready, tmp_path, index=0):
    root, aa_dir, m_dir, names = ready
    output = tmp_path/f'as_{index}'
    result = stage.prepare(output, root, aa_dir, m_dir, names[index])
    assert result['production_execution_allowed'] is False
    return output


def test_two_distinct_noncohort_bindings(ready, tmp_path):
    one = prepared(ready, tmp_path, 0)
    two = prepared(ready, tmp_path, 1)
    first = json.loads((one/'contract_validation.json').read_text())
    second = json.loads((two/'contract_validation.json').read_text())
    assert first['truth_sha256'] != second['truth_sha256']
    assert first['artifact_sha256']['group/noisy.npy'] != second['artifact_sha256']['group/noisy.npy']
    for root in (one, two):
        result = auditor.audit(root, *ready[:3])
        assert result['pass'], result['errors']
        assert result['production_jobs_executed'] == 0


def test_cannot_overwrite_receipt(ready, tmp_path):
    output = prepared(ready, tmp_path)
    with pytest.raises(FileExistsError):
        stage.prepare(output, *ready[:3], ready[3][0])


def test_cross_object_truth_receipt_substitution(ready, tmp_path):
    output = prepared(ready, tmp_path)
    engine = ready[0]/'engine'
    a = engine/'groups'/'engineering_alpha__seed_a__same'/'receipt.json'
    b = engine/'groups'/'engineering_beta__seed_a__same'/'receipt.json'
    shutil.copyfile(b, a)
    result = auditor.audit(output, *ready[:3])
    assert not result['pass']
    assert any('mismatch' in e or 'drift' in e for e in result['errors'])


def test_cross_group_measurement_substitution(ready, tmp_path):
    output = prepared(ready, tmp_path)
    engine = ready[0]/'engine'
    a = engine/'groups'/'engineering_alpha__seed_a__same'/'noisy.npy'
    b = engine/'groups'/'engineering_beta__seed_a__same'/'noisy.npy'
    shutil.copyfile(b, a)
    assert not auditor.audit(output, *ready[:3])['pass']


def test_modified_ray_order_rejected(ready, tmp_path):
    output = prepared(ready, tmp_path)
    job = ready[0]/'engine'/'jobs'/ready[3][0]
    with (job/'order.npy').open('ab') as f:
        f.write(b'changed')
    assert not auditor.audit(output, *ready[:3])['pass']


def test_modified_mart_parameters_rejected(ready, tmp_path):
    output = prepared(ready, tmp_path)
    job = ready[0]/'engine'/'jobs'/ready[3][0]
    p = job/'source.json'
    record = an.read(p)
    record['epochs'] = 99
    p.write_bytes(an.canonical(record))
    assert not auditor.audit(output, *ready[:3])['pass']


def test_receipt_tampering_rejected(ready, tmp_path):
    output = prepared(ready, tmp_path)
    p = output/'contract_validation.json'
    record = json.loads(p.read_bytes())
    record['environment_sha256'] = '0'*64
    p.write_bytes(stage.canonical(record))
    assert not auditor.audit(output, *ready[:3])['pass']


def test_unlisted_job_refused(ready, tmp_path):
    with pytest.raises(ValueError):
        stage.prepare(tmp_path/'as_unknown', *ready[:3], 'prospective__940411__same__information_diag')


def test_checkpoint_not_silently_accepted(ready, tmp_path):
    output = prepared(ready, tmp_path)
    job = ready[0]/'engine'/'jobs'/ready[3][0]
    (job/'checkpoints'/'cp_invalid').mkdir()
    assert not auditor.audit(output, *ready[:3])['pass']


def test_no_unsafe_execution_api():
    assert not hasattr(stage, 'run')
    assert not hasattr(stage, 'dispatch')
    assert not hasattr(stage, 'enable_production')
    assert stage.SCHEMA.endswith('validation-v1')


def test_environment_drift_rejected(ready, tmp_path, monkeypatch):
    output = prepared(ready, tmp_path)
    original = stage.environment
    monkeypatch.setattr(stage, 'environment',
                        lambda: {**original(), 'numpy': 'unexpected-version'})
    assert not auditor.audit(output, *ready[:3])['pass']


def test_checkpoint_receipt_not_misrepresented(ready, tmp_path):
    output = prepared(ready, tmp_path)
    record = json.loads((output/'contract_validation.json').read_bytes())
    assert record['checkpoint_sha256'] == {}
    assert record['rows_done_on_validation'] == 0
    assert record['does_not_run_reconstruction'] is True
    assert record['not_a_production_authorization'] is True
