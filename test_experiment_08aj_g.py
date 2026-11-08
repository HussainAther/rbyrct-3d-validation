import numpy as np
import pytest
from scipy import sparse
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_d import SEEDS
from experiment_08aj_e import full_resolution_pair
from experiment_08aj_g import (measurement_seed,add_shared_prefix,fair_orders,
    paired_catalogue,sampled_noisy_values,fixture,run,INDIVIDUAL)


def test_noise_seed_deterministic_and_policy_free():
    seed=SEEDS['localized_defects'][0]
    s=measurement_seed('localized_defects',seed,940411,'same')
    assert s==measurement_seed('localized_defects',seed,940411,'same')
    assert s!=measurement_seed('localized_defects',seed,940829,'same')
    assert s!=measurement_seed('localized_defects',seed,940411,'independent')
    with pytest.raises(ValueError,match='unregistered'):
        measurement_seed('localized_defects',970099,940411,'same')


def test_prefix_deduplication_and_original_order_preserved():
    raw=np.array([6,1,2,3,4,5,0,7],dtype=np.int64)
    result=add_shared_prefix(np.array([0,6]),raw,6,8)
    assert result.tolist()==[0,6,1,2,3,4]
    with pytest.raises(ValueError):
        add_shared_prefix(np.array([1,1]),raw,6,8)


def test_full_view_exempt_and_warm_prefix():
    A=system_matrix(8,4,TILTS).tocsr()
    orders,prefix=fair_orders(A,n=8,angles=4,seed=940411,budget=128,warm=8,pool=8,batch=8)
    assert len(orders)==5
    assert all(np.array_equal(orders[p][:8],prefix) for p in INDIVIDUAL)
    assert len(np.unique(orders['complete_view']//64))==2
    assert all(np.sum(orders['complete_view']//64==v)==64 for v in np.unique(orders['complete_view']//64))
    assert len({tuple(o.tolist()) for o in orders.values()})==5


def test_nondivisible_complete_view_budget_rejected():
    A=system_matrix(8,4,TILTS).tocsr()
    with pytest.raises(ValueError,match='divisible'):
        fair_orders(A,n=8,angles=4,seed=940411,budget=127,warm=8,pool=8,batch=8)


def test_paired_noise_shared_on_overlapping_ray_ids():
    A=system_matrix(8,4,TILTS).tocsr()
    t,f=full_resolution_pair('smooth_heterogeneity',970099,8)
    obj=SEEDS['smooth_heterogeneity'][0]
    cat=paired_catalogue(A,t,f,family='smooth_heterogeneity',object_seed=obj,
          acquisition_seed=940411,model='same',n=8,angles=4)
    a=np.array([1,9,17,31]);b=np.array([31,17,3,9])
    av=sampled_noisy_values(cat,a);bv=sampled_noisy_values(cat,b)
    assert av[1]==bv[3] and av[2]==bv[1] and av[3]==bv[0]
    cat2=paired_catalogue(A,t,f,family='smooth_heterogeneity',object_seed=obj,
          acquisition_seed=940411,model='same',n=8,angles=4)
    assert np.array_equal(cat['noisy'],cat2['noisy'])


def test_invalid_measurement_catalogue_rejected():
    with pytest.raises(ValueError,match='invalid noise'):
        sampled_noisy_values({'noisy':np.array([1.,np.nan])},np.array([0]))
    with pytest.raises(ValueError,match='invalid acquisition'):
        sampled_noisy_values({'noisy':np.ones(4)},np.array([0,0]))


def test_no_outcomes_in_fixture():
    report=fixture()
    assert report['verdict']=='FAIRNESS_PREFLIGHT_PASS'
    assert report['no_confirmatory_outcomes'] and not report['frozen']
    assert not any('rmse' in k or 'gain' in k for k in report)


def test_no_overwrite(tmp_path):
    destination=tmp_path/'out'
    result=run(destination)
    assert result['verdict']=='FAIRNESS_PREFLIGHT_PASS'
    with pytest.raises(FileExistsError):
        run(destination)
