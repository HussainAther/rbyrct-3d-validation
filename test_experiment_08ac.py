"""08AC: source-locked protocol and object-level accounting tests."""
from pathlib import Path
import csv
import json
import numpy as np
import pytest
from experiment_08ac import (
    SIZE, ALPHA, BUDGET, CHECKPOINTS, OBJECT_SEEDS, ACQUISITION_SEEDS, POLICIES,
    MODELS, PRIMARY_CHECKPOINT, source_fingerprints, freeze, check_lock,
    write_csv, validate_orders, object_summary, aggregate,
)
from experiment_08z import spatial_blend, spatial_novelty, sensitivity_gini
from experiment_08u import select_full
from experiment_08z import select_full_spatial
from scipy import sparse


def test_prespecified_scale_and_alpha():
    assert SIZE == 32 and BUDGET == 1024 and PRIMARY_CHECKPOINT == 1024
    assert ALPHA == .25 and CHECKPOINTS == (512, 1024)


def test_object_seeds_fresh_and_distinct():
    old = {820101 + 7919*i for i in range(8)} | {880201,880202,880203,890201,890202,890203,890204,900201,900202,900203,900204,910201,910202,910203,910204}
    assert len(OBJECT_SEEDS) == len(set(OBJECT_SEEDS)) == 6
    assert not old.intersection(OBJECT_SEEDS)
    assert len(set(ACQUISITION_SEEDS)) == 2


def test_fixed_alpha_zero_recovers_full_on_toy():
    A = sparse.csr_matrix(np.random.default_rng(17).uniform(.01, .7, size=(42, 24)))
    warm = np.arange(5)
    kw = dict(warm_rays=5,batch=4,candidate_pool=5)
    original, _ = select_full(A, None, warm, 18, 7, **kw)
    restored, _ = select_full_spatial(A, None, warm, 18, 7, alpha=0., size=4, **kw)
    assert np.array_equal(original, restored)


def test_spatial_reward_unchanged_and_geometry_only():
    A = sparse.csr_matrix([[3., 1.], [1., 3.]])
    assert np.allclose(spatial_novelty(A, [0,1], [3.,0.]), [-2.25, -.75])
    assert spatial_blend([1,2],[-3,0],.25)[1] > spatial_blend([1,2],[-3,0],.25)[0]
    assert sensitivity_gini(A,[0]) > 0


def test_orders_reject_repeat_and_wrong_warm():
    valid = {p: np.arange(BUDGET) for p in POLICIES}
    validate_orders(valid, valid['coverage'])
    bad = dict(valid)
    bad['information_full'] = np.zeros(BUDGET,dtype=int)
    with pytest.raises(RuntimeError): validate_orders(bad, valid['coverage'])


def test_write_csv_no_empty(tmp_path):
    with pytest.raises(ValueError): write_csv(tmp_path/'none.csv',[])
    write_csv(tmp_path/'yes.csv',[{'a':1,'b':'x'}])
    assert list(csv.DictReader((tmp_path/'yes.csv').open()))[0]['a'] == '1'


def test_object_aggregation_paired_not_pseudoreplicated():
    rows=[]
    for obj in OBJECT_SEEDS:
        for k in CHECKPOINTS:
            for p in POLICIES:
                for seed in ACQUISITION_SEEDS:
                    for model in MODELS:
                        rows.append(dict(object_id=str(obj),acquired=k,policy=p,model=model,
                            acquisition_seed=seed,gain_vs_coverage=.1 if obj == OBJECT_SEEDS[0] else -.1,
                            defect_gain_vs_coverage=.2,nondefect_gain_vs_coverage=.3,global_rmse=.5))
    objects=object_summary(rows)
    assert len(objects) == 6*2*4
    assert all(x['n_conditions'] == 4 for x in objects)
    sums=aggregate(objects)
    assert len(sums) == 8
    assert sums[0]['n_objects'] == 6
    assert sums[0]['object_global_wins'] == 1


def test_object_aggregation_rejects_missing_condition():
    with pytest.raises(RuntimeError):object_summary([dict(object_id='test',acquired=512,policy='coverage',model='same',acquisition_seed=1)])


def test_freeze_lock_source_fingerprints_if_available(tmp_path):
    try:
        source_fingerprints()
    except FileNotFoundError:
        pytest.skip('full legacy modules only available in Windows research repo')
    lock=tmp_path/'lock.json'
    freeze(lock)
    assert check_lock(lock)['spatial_alpha'] == .25
    with pytest.raises(FileExistsError):freeze(lock)
    payload=json.loads(lock.read_text())
    payload['spatial_alpha']=.2
    lock.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError):check_lock(lock)
