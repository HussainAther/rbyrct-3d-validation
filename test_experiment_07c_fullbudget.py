import csv
import json
import numpy as np
import pytest
from experiment_07c_fullbudget import run, validate_config, check_acquisition


def small_args():
    return dict(n=4,angles=2,budget=48,warm=12,batch=6,pool=8,
                provisional_epochs=2,final_epochs=2,allow_test_scale=True)


def test_freeze_rejects_changes():
    with pytest.raises(ValueError, match='fixed'):
        validate_config(8,2,48,12,6,8,2,2,.25,.05,707031,False)


def test_invalid_budgets():
    with pytest.raises(ValueError,match='invalid'):
        validate_config(4,2,12,12,6,8,2,2,.25,.05,707031,True)
    with pytest.raises(ValueError,match='invalid'):
        validate_config(4,2,47,12,6,8,2,2,.25,.05,707031,True)


def test_acquired_only_invariant_rejects_invalid():
    class Oracle:
        allowed={0,1}
    class A:
        shape=(5,3)
    assert np.array_equal(check_acquisition([0,1],Oracle(),2,A()),[0,1])
    with pytest.raises(RuntimeError):check_acquisition([0,0],Oracle(),2,A())


def test_complete_tiny_run(tmp_path):
    out=tmp_path/'run'
    profile,rows=run(out,**small_args())
    assert profile['full_budget_adaptive_measured'] is True
    assert profile['size']==4 and profile['csr_storage_bytes']>0
    assert len(rows)==3 and {r['policy'] for r in rows}=={'coverage','gradient','guarded_05'}
    assert all(r['unique_rays']==48 and r['acquired_only_pass'] for r in rows)
    assert all(r['positive_finite_MART_pass'] for r in rows)
    assert rows[0]['additional_policy_selection_s']==0
    assert len({r['ray_order_sha256'] for r in rows})>=2
    assert all(r['total_selection_including_common_s'] >= r['common_coverage_order_s'] for r in rows)
    assert len(list(csv.DictReader((out/'policy_timing.csv').open())))==3
    assert json.loads((out/'protocol.json').read_text())['no_reconstruction_accuracy_assessment']


def test_no_overwrite(tmp_path):
    out=tmp_path/'run'
    run(out,**small_args())
    with pytest.raises(ValueError,match='overwrite'):
        run(out,**small_args())
