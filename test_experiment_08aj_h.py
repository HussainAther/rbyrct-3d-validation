import numpy as np
import pytest
from experiment_08aj_d import SEEDS
from experiment_08aj_h import historical_seed_review,statistical_rules,independent_ray_probe,run


def test_historical_review_scoped(tmp_path):
    (tmp_path/'experiment_08m.py').write_text('OBJECT_SEEDS=(940101,820101)')
    result=historical_seed_review(tmp_path)
    assert result['seed_literal_overlaps']==[940101]
    assert not result['structural_and_generator_independence_established']
    assert len(result['missing_files'])>=1


def test_statistical_rules_are_draft_and_object_level():
    d=statistical_rules()
    assert d['status']=='DRAFT_PENDING_REVIEW'
    assert '24 synthetic objects' in d['phantom_unit']
    assert 'lower 95%' in d['directional_success']


def test_probe_fixed_limits():
    with pytest.raises(ValueError):
        independent_ray_probe(n=64)
    with pytest.raises(ValueError):
        independent_ray_probe(count=65)


def test_no_outcomes_and_no_overwrite(tmp_path):
    root=tmp_path/'h'
    r=run(root,skip_geometry=True,skip_probe=True)
    assert r['lock_readiness']=='NOT_READY'
    assert not r['frozen'] and r['no_confirmatory_outcomes']
    assert r['geometry'] is None and r['independent_ray_probe'] is None
    assert (root/'manifest.sha256').is_file()
    with pytest.raises(FileExistsError):
        run(root,skip_geometry=True,skip_probe=True)


def test_probe_tiny_sample():
    result=independent_ray_probe(count=2)
    assert result['all_values_finite_nonnegative']
    assert not result['full_catalogue_runtime_measured']


def test_roster_has_24_unique_seeds():
    all_seeds=[s for fam in SEEDS.values() for s in fam]
    assert len(all_seeds)==24 and len(set(all_seeds))==24
