"""05B-08B frozen robustness protocol regression tests."""
from pathlib import Path
import csv
import json
import numpy as np
import pytest

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_08b import (new_phantom, nonnegative_noisy_measurements,
                                 run_matched_case, main)


def test_new_objects_reproducible_distinct_and_block_consistent():
    a, fine = new_phantom(4, 2, 'inclusions', 900001)
    again, f2 = new_phantom(4, 2, 'inclusions', 900001)
    alt, _ = new_phantom(4, 2, 'inclusions', 900002)
    assert a.shape == (64,) and fine.shape == (8,8,8)
    assert np.all(a > 0) and np.array_equal(fine, f2) and np.array_equal(a,again)
    assert not np.array_equal(a,alt)
    assert np.allclose(a,fine.reshape(4,2,4,2,4,2).mean(axis=(1,3,5)).ravel())
    for family in ('filaments','laminae','voids'):
        coarse, image = new_phantom(4,2,family,900011)
        assert coarse.shape == (64,) and np.min(image)>0


def test_noise_reproducible_nonnegative_and_zero_unchanged():
    data=np.array([0.,1.,4.,10.])
    assert np.array_equal(data,nonnegative_noisy_measurements(data,0.,4))
    assert np.array_equal(nonnegative_noisy_measurements(data,.5,4),
                          nonnegative_noisy_measurements(data,.5,4))
    assert np.min(nonnegative_noisy_measurements(data,.9,4))>=0
    with pytest.raises(ValueError):
        nonnegative_noisy_measurements(data,-.1,4)


def test_online_oracle_and_matched_policies():
    n=8; angles=2; budget=64
    A=system_matrix(n,angles,TILTS).tocsr()
    truth,fine=new_phantom(n,2,'voids',900001)
    measured=np.asarray(A@truth).ravel()
    warm=voxel_coverage_order(A,n,angles,len(TILTS),budget,104729,8)
    outcomes,orders=run_matched_case(A,measured,truth,warm,n=n,angles=angles,
        budget=budget,acquisition_seed=104729,warm_rays=16,batch=8,candidate_pool=8,
        provisional_epochs=2,mart_epochs=2,relaxation=.25)
    assert len(outcomes)==4 and set(orders)=={'coverage','gradient','capped_gradient','delayed_48'}
    assert all(len(np.unique(order))==budget for order in orders.values())
    assert np.array_equal(orders['coverage'][:48],orders['delayed_48'][:48])
    assert all(np.isfinite(result['rmse']) for result in outcomes)


def test_cli_frozen_protocol_outputs_and_refuses_overwrite(tmp_path):
    out=tmp_path/'case'
    args=['--size','8','--angles','2','--factor','2','--families','inclusions',
          '--objects-per-family','1','--seeds','104729','--models','same',
          '--noise-fractions','0','--budget','64','--warm-rays','16',
          '--batch','8','--candidate-pool','8','--provisional-epochs','2',
          '--mart-epochs','2','--output-dir',str(out)]
    rows=main(args)
    assert len(rows)==4
    with (out/'protocol.json').open() as f:protocol=json.load(f)
    assert protocol['policies']==['coverage','gradient','capped_gradient','delayed_48']
    with (out/'matched_cases.csv').open(newline='') as f: saved=list(csv.DictReader(f))
    assert len(saved)==4
    assert (out/'object_level_summary.csv').exists()
    with pytest.raises(SystemExit):main(args)
