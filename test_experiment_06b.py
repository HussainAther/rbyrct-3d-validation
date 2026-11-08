"""06B preflight tests: no access to future projections, frozen protocol."""
import csv
import json
import numpy as np
import pytest

from experiment_06b import (defect_phantom, validate, run_validation,
                            OBJECT_SEEDS, ETA, POLICIES, analyze)


def test_generator_seeded_and_positive():
    a,f,descr=defect_phantom(6,2,OBJECT_SEEDS[0])
    b,g,_=defect_phantom(6,2,OBJECT_SEEDS[0])
    c,h,_=defect_phantom(6,2,OBJECT_SEEDS[1])
    assert a.shape==(216,) and f.shape==(12,12,12)
    assert np.all(a>0) and np.all(f>0)
    assert np.array_equal(a,b) and np.array_equal(f,g)
    assert not np.array_equal(a,c) and not np.array_equal(f,h)
    assert 2<=descr['n_defects']<=4


def test_production_rejects_tuning():
    from experiment_06b import (SIZE,ANGLES,FACTOR,BUDGET,CHECKPOINTS,WARM,BATCH,POOL,
        PROVISIONAL_EPOCHS,FINAL_EPOCHS,RELAXATION,ACQUISITION_SEEDS,MODELS,
        NOISE_FRACTION,OFFSET,STEP)
    cfg=dict(size=SIZE,angles=ANGLES,factor=FACTOR,budget=BUDGET,
        checkpoints=CHECKPOINTS,warm_rays=WARM,batch=BATCH,pool=POOL,
        provisional_epochs=PROVISIONAL_EPOCHS,final_epochs=FINAL_EPOCHS,
        relaxation=RELAXATION,eta=ETA,object_seeds=OBJECT_SEEDS,
        acquisition_seeds=ACQUISITION_SEEDS,models=MODELS,
        noise_fraction=NOISE_FRACTION,offset=OFFSET,step=STEP)
    validate(**cfg)
    with pytest.raises(ValueError,match='frozen'):
        validate(**dict(cfg,eta=.1))
    with pytest.raises(ValueError,match='frozen'):
        validate(**dict(cfg,size=8))
    with pytest.raises(ValueError,match='frozen'):
        validate(**dict(cfg,object_seeds=(123,)))


def test_primary_aggregation_objects_not_repeated_conditions():
    rows=[]
    for oid, gains in [('a',[.1,.2]),('b',[-.1,-.3])]:
        for j,g in enumerate(gains):
            for p in POLICIES:
                rows.append(dict(object_id=oid,model='same',acquisition_seed=j,
                    policy=p,acquired=288,gain_vs_coverage=g if p=='guarded_05' else 0.))
    obj, primary=analyze(rows,288)
    assert primary['n_objects']==2
    assert primary['primary_object_wins']==1
    assert primary['primary_mean_object_balanced_gain']==pytest.approx(-.025)
    assert not primary['favorable_primary']


def test_end_to_end_tiny_and_immutable(tmp_path):
    dest=tmp_path/'run'
    settings=dict(size=4,angles=2,factor=2,budget=48,checkpoints=(24,36,48),
        warm_rays=12,batch=6,pool=8,provisional_epochs=2,final_epochs=4,
        object_seeds=(OBJECT_SEEDS[0],),acquisition_seeds=(1901,),
        models=('same',),allow_test_scale=True)
    result=run_validation(dest,**settings)
    assert result['pass_engineering_checks']
    assert result['distinct_objects']==1
    assert result['acquisition_histories']==3
    assert result['reconstructions']==9
    assert result['ray_order_rows']==144
    with (dest/'prefix_reconstructions.csv').open(newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==9
    assert all(float(r['rmse'])>=0 for r in rows)
    assert len({r['ray_order_sha256'] for r in rows})>=3
    protocol=json.loads((dest/'protocol.json').read_text())
    assert protocol['allow_test_scale'] and protocol['guard_eta']==ETA
    with pytest.raises(ValueError,match='overwrite'):
        run_validation(dest,**settings)


def test_preserves_prior_seed_separation():
    from experiment_06b import validate
    with pytest.raises(ValueError,match='prior'):
        validate(size=4,angles=2,factor=2,budget=48,
            checkpoints=(24,36,48),warm_rays=12,batch=6,pool=8,
            provisional_epochs=2,final_epochs=4,relaxation=.25,eta=.05,
            object_seeds=(960001,),acquisition_seeds=(1901,),models=('same',),
            noise_fraction=.005,offset=.15,step=.25,allow_test_scale=True)
