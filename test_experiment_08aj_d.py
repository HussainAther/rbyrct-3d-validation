import numpy as np
import pytest
from experiment_08aj_d import phantom,design,FAMILIES,SEEDS,digest_array
from experiment_08aj_d_analysis import summarize


def synthetic_rows(gain=0.03):
    return [{'family':f,'object_seed':s,'acquisition_seed':a,'model':m,'policy':p,
             'rmse_global':1-gain if p=='information_diag' else 1.0}
             for f in FAMILIES for s in SEEDS[f] for a in (940411,940829)
             for m in ('same','independent') for p in ('uniform_multiscale','information_diag')]


def test_design_has_24_unique_seeded_objects():
    d=design()
    assert len(d['objects'])==24 and len({r['object_seed'] for r in d['objects']})==24
    assert d['status']=='DRAFT_NOT_FROZEN'


def test_phantoms_deterministic_and_positive():
    for f in FAMILIES:
        p=phantom(f,SEEDS[f][0],16)
        assert p.shape==(16,)*3 and np.min(p)>0 and np.isfinite(p).all()
        assert digest_array(p)==digest_array(phantom(f,SEEDS[f][0],16))


def test_families_different():
    assert len({digest_array(phantom(f,SEEDS[f][0],16)) for f in FAMILIES})==3


def test_analysis_uses_24_independent_objects():
    r=summarize(synthetic_rows(),replicates=100)
    assert r['object_count']==24 and r['condition_pairs']==96
    assert r['mean_gain']==pytest.approx(.03) and r['directional_criterion_met']


def test_missing_pair_rejected():
    with pytest.raises(ValueError,match='missing'):
        summarize(synthetic_rows()[:-1],replicates=100)


def test_duplicate_pair_rejected():
    rows=synthetic_rows()
    with pytest.raises(ValueError,match='duplicate'):
        summarize(rows+[rows[0]],replicates=100)


def test_invalid_rmse_rejected():
    rows=synthetic_rows(); rows[0]['rmse_global']=0
    with pytest.raises(ValueError,match='positive'):
        summarize(rows,replicates=100)


def test_zero_gain_not_positive():
    r=summarize(synthetic_rows(0),replicates=100)
    assert r['mean_gain']==0 and not r['directional_criterion_met']
