import numpy as np
import pytest
from scipy import sparse
from experiment_08aj_e import (check_order, full_resolution_pair, model_measurements,
                               acquisition_orders, checked_mart, fixture)
from experiment_04b import system_matrix
from experiment_04g import TILTS


def test_forward_pair_deterministic_and_block_average():
    a,f=full_resolution_pair('localized_defects',970099,8)
    b,g=full_resolution_pair('localized_defects',970099,8)
    assert np.array_equal(a,b) and np.array_equal(f,g)
    assert np.allclose(a,f.reshape(8,2,8,2,8,2).mean((1,3,5)).ravel())


def test_distinct_new_phantom_families():
    pairs=[full_resolution_pair(f,970099,8)[0] for f in ('localized_defects','smooth_heterogeneity','irregular_inclusions')]
    assert not np.array_equal(pairs[0],pairs[1])
    assert not np.array_equal(pairs[1],pairs[2])


def test_adapter_both_models_deterministic_and_finite():
    A=system_matrix(8,4,TILTS).tocsr()
    t,f=full_resolution_pair('smooth_heterogeneity',970099,8)
    for model in ('same','independent'):
        clean,noisy=model_measurements(A,t,f,n=8,angles=4,model=model,noise_seed=970119)
        clean2,noisy2=model_measurements(A,t,f,n=8,angles=4,model=model,noise_seed=970119)
        assert clean.shape==(768,) and np.isfinite(clean).all() and np.min(clean)>=0
        assert np.array_equal(clean,clean2) and np.array_equal(noisy,noisy2)


def test_order_rejection():
    for order in ([0,0,1],[0,1,5],[-1,0,1],[0.,1.,2.]):
        with pytest.raises(ValueError,match='invalid acquisition'):
            check_order(np.array(order),3,4)


def test_order_pairing_and_determinism():
    A=system_matrix(8,4,TILTS).tocsr()
    a=acquisition_orders(A,n=8,angles=4,seed=940411,budget=128)
    b=acquisition_orders(A,n=8,angles=4,seed=940411,budget=128)
    assert len(a)==5
    assert all(np.array_equal(a[p],b[p]) for p in a)
    assert np.array_equal(a['information_diag'][:8],a['coverage'][:8])


def test_invalid_measurement_rejected():
    A=sparse.eye(8,format='csr')
    for bad in (np.full(8,np.nan),np.ones(7),np.full(8,-1.)):
        with pytest.raises(ValueError,match='invalid measurements'):
            checked_mart(A,bad,np.array([0,1,2]),epochs=2)


def test_engineering_fixture_has_no_scientific_outcomes():
    r=fixture()
    assert r['verdict']=='PREFLIGHT_PASS' and len(r['policies'])==5
    assert r['no_confirmatory_outcomes'] and not r['frozen']
    assert 'mean_gain' not in r and 'rmse_global' not in r and 'reconstruction' not in r


def test_fixture_rejects_confirmatory_size():
    with pytest.raises(ValueError,match='fixture'):
        fixture(n=32)
