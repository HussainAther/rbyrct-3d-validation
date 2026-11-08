import numpy as np
import pytest
from experiment_08aj_u import features,cohort,precision_sim,build,canonical

def test_features_constant():
    r=features(np.ones((32,32,32))*.4)
    assert r['gradient_rms']==0 and r['above_0_5_fraction']==0

def test_features_reject_bad():
    with pytest.raises(ValueError):features(np.zeros((32,32,32)))

def test_cohorts_and_hashes():
    p,h=cohort()
    assert len(p)==24 and len(h)==8
    assert len({x['sha256'] for x in p+h})==32
    assert {x['cohort'] for x in p}=={'localized_defects','smooth_heterogeneity','irregular_inclusions'}

def test_precision_deterministic():
    a=precision_sim(trials=12,bootstraps=110)
    assert a==precision_sim(trials=12,bootstraps=110)
    assert len(a)==12 and all(0<=r['estimated_coverage']<=1 for r in a)

def test_simulation_rejects_tiny():
    with pytest.raises(ValueError):precision_sim(trials=1)

def test_no_outcomes_or_freeze():
    r=build(trials=12,bootstraps=110)
    assert not r['frozen'] and not r['confirmatory_execution_allowed']
    assert r['no_confirmatory_outcomes']
    assert b'structural_independence_proven' in canonical(r)
