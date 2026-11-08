"""Fast tests: Stage 2 invariants and 4^3 integration smoke, not full 12^3 experiment."""
import csv
import json

import pytest

from experiment_05b_11_stage2 import (FAMILIES, MODELS, POLICIES, SEEDS,
    OBJECT_SEED_BASE, order_sha256, run_stage2, validate_stage2)


def small_kwargs():
    return dict(size=4,angles=2,factor=2,budget=60,checkpoints=(48,60),
        warm_rays=12,batch=12,candidate_pool=8,provisional_epochs=1,
        final_epochs=2,relaxation=.25,families=('inclusions',),
        seeds=(191,),models=('same',),objects_per_family=1,
        object_seed_base=960001,noise_fraction=.005,offset=.15,step=.25,
        allow_test_scale=True)


def test_default_configuration_is_frozen(tmp_path):
    kw=small_kwargs()
    kw['allow_test_scale']=False
    with pytest.raises(ValueError,match='frozen'):
        run_stage2(output_dir=tmp_path/'reject',**kw)


def test_new_objects_do_not_reuse_pilot_or_08b_seeds():
    new={OBJECT_SEED_BASE+1009*i+j for i in range(4) for j in range(2)}
    old={900001+1009*i+j for i in range(4) for j in range(2)}
    assert len(new)==8 and not (new & (old|{950101,950202}))
    assert len(POLICIES)==3 and len(MODELS)==2 and len(SEEDS)==2 and len(FAMILIES)==4


def test_ray_order_hash_changes_with_order():
    assert order_sha256([1,2,3])==order_sha256((1,2,3))
    assert order_sha256([1,2,3])!=order_sha256([3,2,1])


def test_bad_checkpoint_rejected():
    kw=small_kwargs();kw['checkpoints']=(47,60)
    with pytest.raises(ValueError,match='invalid'):
        validate_stage2(**kw)


def test_stage2_end_to_end_smoke(tmp_path):
    out=tmp_path/'smoke'
    status=run_stage2(output_dir=out,**small_kwargs())
    assert status['pass_engineering_checks']
    assert status['distinct_objects']==1
    assert status['acquisition_histories']==3
    assert status['reconstructions']==6
    with (out/'acquisition_orders.csv').open(newline='') as f:
        orders=list(csv.DictReader(f))
    assert len(orders)==180
    by_policy={p:[int(r['ray_id']) for r in orders if r['policy']==p] for p in POLICIES}
    assert by_policy['coverage'][:48]==by_policy['delayed_48'][:48]
    assert all(len(set(v))==60 for v in by_policy.values())
    with (out/'matched_cases.csv').open(newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==3
    assert sum(abs(float(r['gain_vs_coverage']))<1e-14 for r in rows)==1
    config=json.loads((out/'protocol.json').read_text())
    assert config['frozen_test_scale'] is True
    assert (out/'run_manifest.sha256').exists()
    with pytest.raises(ValueError,match='overwrite'):
        run_stage2(output_dir=out,**small_kwargs())
