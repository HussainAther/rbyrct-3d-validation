"""Independent tests for the 07A verifier, no production experiment rerun."""
import csv
import hashlib
import json
import struct
from pathlib import Path
import pytest
from audit_07a import Audit, audit, main, near, sha_prefix, valid_rmse_gain, verify_manifest


def test_prefix_little_endian_i64():
    ids = [0, 1, 128, 1727]
    expected = hashlib.sha256(b''.join(struct.pack('<q', x) for x in ids)).hexdigest()
    assert sha_prefix(ids) == expected
    assert sha_prefix(ids[:-1]) != expected


def test_sha_manifest_detects_corruption(tmp_path):
    for name in ('a.csv','b.json'):
        (tmp_path/name).write_text('original\n')
    manifest = ''.join(f'{hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()}  {name}\n' for name in ('a.csv','b.json'))
    (tmp_path/'run_manifest.sha256').write_text(manifest)
    a=Audit()
    verify_manifest(tmp_path,a)
    # The files aren't the expected production 06B set, but both digests verify.
    assert not any('checksum mismatch' in x for x in a.errors)
    (tmp_path/'a.csv').write_text('modified\n')
    b=Audit(); verify_manifest(tmp_path,b)
    assert any('checksum mismatch' in x for x in b.errors)


def test_relative_float_comparison():
    assert near(0.02917363994669987, 0.02917363994669986)
    assert not near(0.02917363994669987, 0.12917363994669987)


def test_missing_production_inputs_blocked(tmp_path):
    assert main(['--results-dir',str(tmp_path)]) == 2
    with pytest.raises(FileNotFoundError):
        audit(tmp_path)


def test_does_not_create_report_inside_source(tmp_path):
    # Missing inputs block the audit without modifying the directory.
    out=tmp_path/'report.json'
    assert main(['--results-dir',str(tmp_path),'--report',str(out)])==2
    assert not out.exists()


def test_negative_relative_gains_are_valid():
    assert valid_rmse_gain(0.2, -0.25)
    assert valid_rmse_gain(0.3, -5.0)
    assert valid_rmse_gain(0.2, 0.0)
    assert valid_rmse_gain(0.1, 0.999999)
    assert not valid_rmse_gain(0.0, -0.25)
    assert not valid_rmse_gain(-0.2, -0.25)
    assert not valid_rmse_gain(0.2, 1.5)
    import pytest
    with pytest.raises(ValueError):
        valid_rmse_gain(0.2, float('nan'))
