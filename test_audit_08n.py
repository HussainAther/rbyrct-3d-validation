"""Focused independent 08N auditor unit tests; full archived-data test runs on Windows."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pytest
from audit_08n import equal, integer, number, order_hash, sha_array, read_csv, sha, audit


def test_order_digest_matches_numpy_little_endian():
    values=[1,200,4095]
    assert order_hash(values)==hashlib.sha256(np.array(values,dtype='<i8').tobytes()).hexdigest()


def test_order_digest_detects_permutation():
    assert order_hash([1,2,3])!=order_hash([2,1,3])


def test_array_truth_hash_dtype_normalization():
    a=np.array([.1,.5,.9],dtype=np.float32)
    assert sha_array(a)==hashlib.sha256(np.asarray(a,dtype='<f8').tobytes()).hexdigest()


def test_number_rejects_nonfinite():
    for value in ('nan','inf','-inf'):
        with pytest.raises(ValueError):number({'x':value},'x')


def test_integer_rejects_bad_or_noncanonical():
    assert integer({'v':'4096'},'v')==4096
    for value in ('2.0','bad','03'):
        with pytest.raises(ValueError):integer({'v':value},'v')


def test_numeric_tolerance():
    assert equal(.0500423027241302,.05004230272413021)
    assert not equal(.0500423027241302,.0400423027241302)


def test_csv_reader_and_hash(tmp_path):
    p=tmp_path/'data.csv';p.write_text('object_id,global_rmse\na,0.5\n',encoding='utf-8')
    assert read_csv(p)==[{'object_id':'a','global_rmse':'0.5'}]
    h=sha(p);p.write_text('object_id,global_rmse\na,0.6\n',encoding='utf-8')
    assert sha(p)!=h


def test_missing_archive_rejected_before_side_effects(tmp_path):
    lock=tmp_path/'lock.json';lock.write_text('{}')
    with pytest.raises(FileNotFoundError):
        audit(tmp_path/'missing',protocol_lock=lock,source_dir=tmp_path)


def test_cli_requires_paths_and_does_not_create_report(tmp_path, monkeypatch):
    from audit_08n import main
    monkeypatch.setattr(sys,'argv',['audit_08n.py','--results-dir',str(tmp_path),'--report',str(tmp_path/'report.json')])
    with pytest.raises(SystemExit): main()
    assert not (tmp_path/'report.json').exists()


def test_source_has_no_write_to_original_archive():
    import inspect
    from audit_08n import audit
    source=inspect.getsource(audit)
    assert '.write_text(' not in source
    assert '.write_bytes(' not in source


@pytest.mark.skipif(not Path('../rbyrct-results/experiment08m/frozen_first/sha256.json').exists(),
                    reason='08M archived run is on user Windows host')
def test_actual_full_archive_integration():
    lock=Path('protocol_08m_frozen.json')
    if not lock.exists(): pytest.skip('Frozen lock unavailable')
    result=audit('../rbyrct-results/experiment08m/frozen_first',protocol_lock=lock,
                 source_dir='.',check_masks=True)
    assert result['verdict']=='PASS',result['errors']
    assert result['histories_verified']==128
    assert result['checkpoint_rows_verified']==384
    assert equal(result['independently_recalculated_primary']['mean_global_gain'],.0500423027241302)
