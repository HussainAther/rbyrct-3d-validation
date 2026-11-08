import json
import numpy as np
import pytest
from experiment_08aj_b import (uniform_multiscale_order,build_orders,validate_order,
                               profile_prefix,main)

@pytest.mark.parametrize('n,angles,tilts,budget',[(8,4,3,64),(16,4,3,128),(32,4,3,2048),(7,3,2,71)])
def test_catalogue_permutation_and_cycle_balance(n,angles,tilts,budget):
    for order in build_orders(n,angles,tilts,930101).values():
        prefix=validate_order(order,n,angles,tilts,budget)
        data=profile_prefix(prefix,n,angles,tilts)
        assert data['unique_rays']==budget
        assert data['view_counts_max']-data['view_counts_min']<=1

def test_uniform_independent_of_seed():
    assert np.array_equal(build_orders(8,4,3,1)['uniform_multiscale'],
                          build_orders(8,4,3,999)['uniform_multiscale'])

def test_stratified_seed_dependent_and_repeatable():
    a=build_orders(8,4,3,42)['stratified_random_04h']
    b=build_orders(8,4,3,42)['stratified_random_04h']
    c=build_orders(8,4,3,43)['stratified_random_04h']
    assert np.array_equal(a,b) and not np.array_equal(a,c)

def test_dyadic_detector_prefix_is_spread():
    order=uniform_multiscale_order(8,2,2)
    cells=(order[::4][:4]%(8*8))
    quadrants={(int(c)//8//4,int(c)%8//4) for c in cells}
    assert len(quadrants)==4

def test_bad_inputs():
    with pytest.raises(ValueError):uniform_multiscale_order(0,4,3)
    with pytest.raises(AssertionError):validate_order(np.arange(12),8,4,3,100)
    with pytest.raises(ValueError):validate_order(np.arange(8*8*4*3),8,4,3,99999)

def test_smoke_and_no_overwrite(tmp_path):
    root=tmp_path/'testrun'
    result=main(['--smoke','--output-dir',str(root)])
    assert result['size']==8
    assert json.loads((root/'run_status.json').read_text())['complete']
    assert len(list(root.glob('*selected_ray_ids.npy')))==2
    with pytest.raises(FileExistsError):main(['--smoke','--output-dir',str(root)])
