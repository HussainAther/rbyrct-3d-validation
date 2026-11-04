"""05B-07 delayed MART-feedback implementation and causality regression checks."""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_05b_04 import select_order
from experiment_05b_gate import AcquiredOnly
from experiment_05b_07 import select_delayed_order, main


def setup():
    n, angles = 4, 2
    A = system_matrix(n,angles,TILTS).tocsr()
    truth = np.full(n**3,.4)
    observations = np.asarray(A@truth).ravel()
    warm = np.arange(12,dtype=np.int64)
    return A,observations,n,angles,warm


def test_frozen_policy_parity():
    A,obs,n,angles,warm = setup()
    for name in ('coverage','gradient','capped_gradient'):
        expected,_,_ = select_order(A,obs,n,angles,warm,24,271828,policy=name,
                                    warm_rays=12,batch=4,candidate_pool=8,
                                    provisional_epochs=2,relaxation=.25,feature_cap=3.)
        actual,_,_ = select_delayed_order(A,obs,n,angles,warm,24,271828,policy=name,
                                          warm_rays=12,batch=4,candidate_pool=8,
                                          provisional_epochs=2,relaxation=.25,feature_cap=3.)
        assert np.array_equal(actual, expected)


def test_delay_prefix_matches_coverage_and_feedback_flags():
    A,obs,n,angles,warm = setup()
    baseline,_,_ = select_delayed_order(A,obs,n,angles,warm,24,271828,policy='coverage',
                                         warm_rays=12,batch=4,candidate_pool=8,provisional_epochs=2)
    delay,trace,_ = select_delayed_order(A,obs,n,angles,warm,24,271828,policy='delayed_48',
                                         warm_rays=12,batch=4,candidate_pool=8,provisional_epochs=2,
                                         delay_at=20)
    assert np.array_equal(delay[:20],baseline[:20])
    assert [x['feedback_active'] for x in trace] == [0,0,1]


def test_acquired_only_all_policies():
    A,obs,n,angles,warm = setup()
    for name in ('coverage','gradient','capped_gradient','delayed_48','delayed_80'):
        guard = AcquiredOnly(obs)
        guard.commit(warm)
        kwargs = {'delay_at': 20} if name.startswith('delayed_') else {}
        order,_,_ = select_delayed_order(A,guard,n,angles,warm,24,271828,policy=name,
                                         warm_rays=12,batch=4,candidate_pool=8,
                                         provisional_epochs=2,**kwargs)
        assert len(set(order)) == 24


def test_bad_switch_rejected():
    A,obs,n,angles,warm = setup()
    with pytest.raises(ValueError):
        select_delayed_order(A,obs,n,angles,warm,24,271828,policy='delayed_48',
                             warm_rays=12,batch=4,delay_at=18)


def test_small_cli_outputs(tmp_path):
    dest = tmp_path/'pilot'
    # Use 4^3 smoke with 12 warm, 4 batches, 84 total rays to permit 48/80 switches.
    result = main(['--size','4','--angles','2','--factor','2',
                   '--phantoms','branches','--representations','replicated',
                   '--seeds','271828','--warm-rays','12','--batch','4',
                   '--budget','84','--candidate-pool','8','--provisional-epochs','2',
                   '--mart-epochs','3','--checkpoints','12','48','80','84',
                   '--output-dir',str(dest)])
    assert len(result) == 5
    with (dest/'delayed_feedback.csv').open(newline='',encoding='utf8') as stream:
        data = list(csv.DictReader(stream))
    assert len(data) == 5
    assert len({r['policy'] for r in data}) == 5
    assert json.loads((dest/'protocol.json').read_text())['n_cases'] == 1
