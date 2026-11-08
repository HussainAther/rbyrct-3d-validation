from pathlib import Path
import json
import pytest
import experiment_08aj_p as p


def test_smoke(tmp_path):
    target = tmp_path / 'preflight'
    result = p.run(target, smoke=True)
    assert result['complete'] and result['deterministic']
    assert result['no_phantoms_or_reconstruction']
    assert result['voxel_count'] == 512
    assert (target / 'profile.json').is_file()
    assert json.loads((target / 'run_status.json').read_text())['complete']
    assert (target / '08aj_p_assessment.sha256').is_file()


def test_no_overwrite(tmp_path):
    target = tmp_path / 'existing'
    target.mkdir()
    with pytest.raises(FileExistsError):
        p.run(target, smoke=True)


def test_invalid_resource_gate(tmp_path):
    with pytest.raises(ValueError):
        p.run(tmp_path / 'new', smoke=True, max_rss_gib=0)
