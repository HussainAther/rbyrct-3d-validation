import json
import numpy as np
import pytest
from experiment_08aj_c_view import complete_view_order, select_views, report, main, directions


def test_source_view_geometry_and_indexing():
    d=directions(4,(-20,0,20))
    assert d.shape==(12,3)
    assert np.allclose(np.linalg.norm(d,axis=1),1)
    ids,views=complete_view_order(8,4,(-20,0,20),128)
    assert len(ids)==128 and len(views)==2
    assert len(set(ids))==128
    for v, block in zip(views,ids.reshape(2,64)):
        assert np.array_equal(block,np.arange(int(v)*64,(int(v)+1)*64))


def test_repeatability_and_view_spacing():
    a,v=complete_view_order(32,4,(-20,0,20),2048)
    b,w=complete_view_order(32,4,(-20,0,20),2048)
    assert np.array_equal(a,b) and np.array_equal(v,w)
    assert v[0]==4
    assert len(v)==len(set(v))


def test_invalid_budgets_and_boundary():
    with pytest.raises(ValueError,match='INFEASIBLE_COMPLETE_VIEWS'):
        complete_view_order(64,4,(-20,0,20),2048)
    with pytest.raises(ValueError,match='catalogue'):
        complete_view_order(8,4,(-20,0,20),13*64)
    with pytest.raises(ValueError,match='INFEASIBLE_COMPLETE_VIEWS'):
        complete_view_order(32,4,(-20,0,20),1)
    a,_=complete_view_order(64,4,(-20,0,20),4096)
    assert len(a)==4096


def test_no_outcome_and_infeasible_reporting():
    r,ids=report(64,4,(-20,0,20),2048)
    assert r['verdict']=='INFEASIBLE' and ids is None
    assert r['no_outcome_data'] and not r['physical_scanner_validated']


def test_cli_writes_and_no_overwrite(tmp_path):
    out=tmp_path/'trial'
    r=main(['--size','8','--budget','128','--output-dir',str(out)])
    assert r['verdict']=='PASS'
    assert (out/'complete_view_selected_ray_ids.npy').exists()
    assert json.loads((out/'run_status.json').read_text())['verdict']=='PASS'
    with pytest.raises(FileExistsError):
        main(['--size','8','--budget','128','--output-dir',str(out)])


def test_cli_infeasibility_is_explicit(tmp_path):
    out=tmp_path/'infeasible'
    r=main(['--size','64','--budget','2048','--output-dir',str(out)])
    assert r['verdict']=='INFEASIBLE'
    assert not (out/'complete_view_selected_ray_ids.npy').exists()
    assert json.loads((out/'run_status.json').read_text())['verdict']=='INFEASIBLE'
