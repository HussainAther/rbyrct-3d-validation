"""08E pure math/integrity tests; full repository integration runs on Windows."""
import numpy as np
import pytest
from scipy.sparse import csr_matrix
from experiment_08e import score_rank,contrast,row_geometry,retrospective,acquire_with_probes


def test_ranking_deterministic_ties():
    assert score_rank([.8,.8,.2],[7,3,5]).tolist()==[1,0,2]


def test_invalid_scores_rejected():
    with pytest.raises(ValueError):score_rank([float('nan')],[1])
    with pytest.raises(ValueError):score_rank([1,2],[3,3])


def test_correlation_and_degeneracy():
    assert np.isclose(contrast([1,2,3],[2,4,6]),1)
    assert np.isnan(contrast([1,1,1],[2,3,4]))
    with pytest.raises(ValueError):contrast([1,2],[1])


def test_geometry_evaluation():
    A=csr_matrix(np.array([[1.,0.,2.],[0.,3.,0.]]))
    hit,frac,red=row_geometry(A,0,np.array([2.,0.,5.]),np.array([False,False,True]))
    assert hit==1 and np.isclose(frac,2/3) and np.isclose(red,4)


def test_selector_and_retro_boundaries():
    import inspect
    source=inspect.getsource(acquire_with_probes)
    assert 'defect_support' not in source and 'truth' not in source
    assert 'oracle_values' not in source and 'error_metrics' not in source
    retro=inspect.getsource(retrospective)
    assert 'oracle_values[new_ids]' in retro


def test_no_overwrite_guard_in_source():
    import inspect
    from experiment_08e import run
    assert "FileExistsError('refusing to overwrite diagnostics')" in inspect.getsource(run)
