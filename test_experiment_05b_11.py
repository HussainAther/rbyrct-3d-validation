"""Fast regression tests for 05B-11 Stage 1 pilot; do not execute full 12^3 suite."""
import csv
import json
import numpy as np
import pytest
from experiment_05b_11 import (sha_order,validate_pilot_settings,run_pilot,
                                OBJECT_SEEDS)


def test_new_object_seeds_are_distinct_from_08b():
    prior={900001+i*1009+j for i in range(4) for j in range(2)}
    assert not prior.intersection(OBJECT_SEEDS.values())
    assert len(set(OBJECT_SEEDS.values()))==2


def test_order_digest_is_deterministic():
    assert sha_order([1,2,3]) == sha_order(np.array([1,2,3],dtype=np.int32))
    assert sha_order([1,2,3]) != sha_order([3,2,1])


def test_invalid_geometry_and_checkpoints_rejected():
    with pytest.raises(ValueError):
        validate_pilot_settings(12,4,2,288,(145,288),36,12,24,4,16,.25)
    with pytest.raises(ValueError):
        validate_pilot_settings(12,4,2,288,(144,288),35,12,24,4,16,.25)
    with pytest.raises(ValueError):
        validate_pilot_settings(12,4,2,288,(144,288),36,12,24,4,16,-.1)


def test_pilot_smoke_outputs_and_no_overwrite(tmp_path):
    dest=tmp_path/'pilot'
    result=run_pilot(size=4,angles=2,factor=2,budget=60,
      checkpoints=(48,60),warm_rays=12,batch=12,candidate_pool=8,
      provisional_epochs=1,final_epochs=2,output_dir=dest,families=('inclusions',))
    assert len(result)==6
    assert (dest/'run_manifest.sha256').exists()
    engineering=json.loads((dest/'engineering_status.json').read_text())
    assert engineering['pass_engineering_checks']
    with (dest/'acquisition_orders.csv').open(newline='') as f:
        order=list(csv.DictReader(f))
    assert len(order)==180
    coverage=[int(r['ray_id']) for r in order if r['policy']=='coverage']
    delayed=[int(r['ray_id']) for r in order if r['policy']=='delayed_48']
    assert coverage[:48]==delayed[:48]
    for policy in ('coverage','gradient','delayed_48'):
        rayids=[int(r['ray_id']) for r in order if r['policy']==policy]
        assert len(set(rayids))==60
    with pytest.raises(ValueError,match='overwrite'):
        run_pilot(size=4,angles=2,factor=2,budget=60,
         checkpoints=(48,60),warm_rays=12,batch=12,candidate_pool=8,
         provisional_epochs=1,final_epochs=2,output_dir=dest,families=('inclusions',))
