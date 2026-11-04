import json
from pathlib import Path
import numpy as np
import pytest
from experiment_07c_preflight import defect_support,error_metrics,verify_config,run


def test_mask_deterministic_nonempty():
    a,info=defect_support(8,2,707001)
    b,info2=defect_support(8,2,707001)
    assert np.array_equal(a,b)
    assert info==info2
    assert 0<a.sum()<8**3
    assert info['evaluation_only'] is True


def test_mask_changes_by_seed():
    a,_=defect_support(8,2,707001)
    b,_=defect_support(8,2,707002)
    assert not np.array_equal(a,b)


def test_error_metric_mask_partition():
    true=np.ones(8)
    x=true.copy();x[0]=3;x[4]=2
    m=np.array([True]*4+[False]*4)
    v=error_metrics(x,true,m)
    assert v['global_rmse']==pytest.approx(np.sqrt(5/8))
    assert v['defect_region_rmse']==pytest.approx(1.)
    assert v['nondefect_rmse']==pytest.approx(.5)
    with pytest.raises(ValueError):error_metrics(x,true,np.ones(8,bool))


def test_production_freeze_and_invalid():
    with pytest.raises(ValueError,match='fixed'):
        verify_config(8,2,48,72,12,6,8,2,4,.25,.05,707031,False)
    with pytest.raises(ValueError):
        verify_config(4,2,48,24,12,6,8,2,4,.25,.05,707031,True)


def test_end_to_end_tiny_and_nonoverwrite(tmp_path):
    target=tmp_path/'smoke'
    prof,rows,mask=run(target,n=4,angles=2,small_budget=24,large_budget=48,
       warm=12,batch=6,pool=8,provisional_epochs=2,final_epochs=2,
       allow_test_scale=True)
    assert prof['size']==4 and prof['max_profiled_adaptive_budget']==24
    assert len(rows)==4 and all(r['acquired_only_pass'] for r in rows)
    assert len({r['ray_sha256'] for r in rows})>=2
    assert mask['mask_voxels']>0
    assert json.loads((target/'protocol.json').read_text())['test_scale'] is True
    assert (target/'policy_timing.csv').exists()
    with pytest.raises(ValueError,match='overwrite'):
        run(target,n=4,angles=2,small_budget=24,large_budget=48,
           warm=12,batch=6,pool=8,provisional_epochs=2,final_epochs=2,
           allow_test_scale=True)
