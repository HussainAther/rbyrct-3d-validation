"""08AJ-I no-outcome engineering audit tests."""
import csv
import io
import json
import zipfile
from pathlib import Path
import numpy as np
import pytest
from experiment_08aj_i import archive_manifests, historical_audit, full_projector_engineering, run, HISTORICAL


def fake_objects():
    return [{'object_seed':940101,'coarse_truth_sha256':'a'*64,'fine_truth_sha256':'b'*64}]


def make_zip(path,seed='810101',truth='c'*64):
    with zipfile.ZipFile(path,'w') as z:
        for name in HISTORICAL:
            z.writestr(f'collection/{name}/run/object_manifest.csv',
                       'object_seed,truth_sha256\n'+seed+','+truth+'\n')


def test_historical_zip_complete(tmp_path):
    archive = tmp_path/'history.zip';make_zip(archive)
    a=historical_audit(archive,fake_objects())
    assert a['exact_overlap_audit_complete'] and len(a['manifests'])==6
    assert not a['seed_overlaps'] and not a['coarse_truth_hash_overlaps']
    assert not a['generator_and_structural_independence_established']


def test_detects_seed_and_truth_overlap(tmp_path):
    archive=tmp_path/'history.zip';make_zip(archive,seed='940101',truth='a'*64)
    a=historical_audit(archive,fake_objects())
    assert a['seed_overlaps']==['940101']
    assert a['coarse_truth_hash_overlaps']==['a'*64]


def test_incomplete_history_is_flagged(tmp_path):
    p=tmp_path/'archive';p.mkdir()
    d=p/'experiment08m'/'run';d.mkdir(parents=True)
    (d/'object_manifest.csv').write_text('object_seed,truth_sha256\n100101,'+'c'*64+'\n')
    a=historical_audit(p,fake_objects())
    assert not a['exact_overlap_audit_complete']
    assert a['historical_studies_covered']['experiment08m']
    assert not a['historical_studies_covered']['experiment08ac']


def test_missing_archive_flags_incomplete(tmp_path):
    a=historical_audit(tmp_path/'absent',fake_objects())
    assert not a['exact_overlap_audit_complete']
    assert a['parsing_errors']


def test_full_projector_uses_nonroster_seed():
    with pytest.raises(ValueError):
        full_projector_engineering(seed=940101)


def test_no_overwriting_or_freezing(tmp_path):
    out=tmp_path/'occupied';out.mkdir()
    with pytest.raises(FileExistsError):
        run(out,tmp_path,skip_projection=True)


def test_small_projector_math_mini():
    # Unit-level full intended ray-march operator tested at a miniature 8^3 geometry.
    from experiment_04qa import project
    from experiment_04g import TILTS
    x=np.full((16,16,16),0.25)
    a=project(x,8,4,TILTS,factor=2,step=0.5,mode='linear')
    assert a.shape==(768,) and np.isfinite(a).all() and (a>=0).all()


def test_windows_style_manifest_paths_are_covered(monkeypatch):
    import experiment_08aj_i as mod
    content = b'object_seed,truth_sha256\n100101,' + b'c'*64 + b'\n'
    entries = [(f'{name}\\run\\object_manifest.csv', content) for name in HISTORICAL]
    monkeypatch.setattr(mod, 'archive_manifests', lambda location: (entries, []))
    result = mod.historical_audit('mock-windows-directory', fake_objects())
    assert result['exact_overlap_audit_complete']
    assert all(result['historical_studies_covered'].values())
