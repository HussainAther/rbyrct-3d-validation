"""08AJ-F draft reconciliation checks, strictly no scientific outcomes."""
import json
import numpy as np
import pytest
from experiment_08aj_d import FAMILIES,SEEDS,phantom,digest_array,design as old_design
from experiment_08aj_f import reconciled_object,design,run
from experiment_08aj_e import full_resolution_pair


def test_reconciled_pair_has_correct_block_average():
    r=reconciled_object('localized_defects',SEEDS['localized_defects'][0])
    coarse,fine=full_resolution_pair('localized_defects',SEEDS['localized_defects'][0],32)
    expected=fine.reshape(32,2,32,2,32,2).mean((1,3,5))
    assert np.array_equal(coarse,expected.ravel())
    assert r['fine_truth_sha256']==digest_array(fine)
    assert r['coarse_truth_sha256']==digest_array(expected)


def test_24_unique_objects_and_historical_roster_unchanged():
    d=design()
    old=old_design()
    assert len(d['objects'])==len(old['objects'])==24
    assert [(x['family'],x['object_seed']) for x in d['objects']]==[(x['family'],x['object_seed']) for x in old['objects']]
    assert len({x['coarse_truth_sha256'] for x in d['objects']})==24
    assert len({x['fine_truth_sha256'] for x in d['objects']})==24


def test_reconciliation_records_changed_hashes_not_overwrite():
    d=design()
    assert any(x['changed_from_08aj_d_direct_truth'] for x in d['objects'])
    for x in d['objects']:
        original=digest_array(phantom(x['family'],x['object_seed'],32))
        assert x['old_direct_32_truth_sha256']==original


def test_no_outcomes_and_freeze_refused():
    d=design()
    assert d['frozen'] is False and d['lock_readiness']=='NOT_READY'
    assert d['no_reconstruction_or_outcome_data']
    assert not any(k in d for k in ('rmse','mean_gain','policy_wins'))


def test_source_hashes_present():
    d=design()
    assert 'experiment_08aj_f.py' in d['source_sha256']
    assert 'experiment_08aj_e.py' in d['source_sha256']


def test_frozen_output_paths_rejected(tmp_path):
    path=tmp_path/'reconciled'
    status=run(path)
    assert status['verdict']=='RECONCILIATION_PASS'
    assert json.loads((path/'run_status.json').read_text())['no_outcome_data']
    with pytest.raises(FileExistsError):run(path)


def test_unknown_family_seed_or_size_rejected():
    for args in [('no_such_family',940101,32),('localized_defects',999,32),('localized_defects',940101,64)]:
        with pytest.raises(ValueError):reconciled_object(*args)


def test_open_blockers_not_conflated_with_reconciliation():
    d=design()
    assert d['open_or_partial_count']>=1
    assert any(x['id']=='F3_warm_prefix_fairness' and x['status']=='OPEN' for x in d['lock_items'])
