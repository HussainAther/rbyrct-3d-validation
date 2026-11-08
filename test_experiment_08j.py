from __future__ import annotations
import numpy as np
import pytest
from scipy import sparse
from experiment_08j import diagonal_precision, info_score, summarize, run


def test_diagonal_exact_hand_calculation():
    a=sparse.csr_matrix([[1.,2.],[0.,1.]])
    d=diagonal_precision(a,prior_variance=2.,observation_variance=1.)
    np.testing.assert_allclose(d,[1/1.5,1/5.5])
    c=sparse.csr_matrix([[1.,1.],[2.,0.]])
    expected=[(d[0]**2+d[1]**2)/(1+d[0]+d[1]),4*d[0]**2/(1+4*d[0])]
    np.testing.assert_allclose(info_score(a,c,prior_variance=2.),expected)


def test_rank_one_trace_identity():
    a=sparse.csr_matrix([[1.,0.],[0.,2.]])
    c=sparse.csr_matrix([[1.,3.]])
    d=diagonal_precision(a)
    x=c.toarray().ravel();D=np.diag(d)
    Dpost=D-np.outer(D@x,D@x)/(1+x@D@x)
    assert np.isclose(np.trace(D)-np.trace(Dpost),info_score(a,c)[0])


def test_zero_ray_nonnegative_and_diagonal_precision_shrinks():
    a=sparse.csr_matrix([[1.,0.,1.]])
    b=sparse.csr_matrix([[1.,0.,1.],[1.,0.,1.]])
    c=sparse.csr_matrix([[1.,1.,0.],[0.,0.,0.]])
    score=info_score(a,c)
    assert score[0]>0 and score[1]==0
    assert np.all(diagonal_precision(b)<=diagonal_precision(a))


def test_invalid_inputs_and_no_measurement_argument():
    a=sparse.csr_matrix([[1.,2.]])
    c=sparse.csr_matrix([[1.,2.]])
    for parameter in ({'prior_variance':0},{'observation_variance':-1},
                      {'prior_variance':float('nan')},{'observation_variance':float('inf')}):
        with pytest.raises(ValueError):info_score(a,c,**parameter)
    with pytest.raises(TypeError):info_score(a.toarray(),c)
    with pytest.raises(TypeError):info_score(a,c.toarray())
    with pytest.raises(TypeError):info_score(a,c,candidate_measurements=np.array([1.]))
    with pytest.raises(ValueError):info_score(a,sparse.csr_matrix([[1.,2.,3.]]))


def test_deterministic_and_permutation_equivariant():
    a=sparse.csr_matrix([[1.,2.,3.],[2.,0.,1.]])
    c=sparse.csr_matrix([[1.,1.,0.],[0.,2.,3.],[3.,1.,0.]])
    s=info_score(a,c)
    np.testing.assert_array_equal(s,info_score(a,c))
    np.testing.assert_allclose(s[[2,0,1]],info_score(a,c[[2,0,1]]))


def test_pool_summary_selected_and_regret():
    rows=[]
    for obj in (1,2):
        for j,(info,grad,dg,gg) in enumerate([(3.,1.,.06,.02),(2.,3.,.01,.01),(1.,2.,.02,.03)]):
            rows.append(dict(size=12,policy='gradient',object_seed=obj,acquired_before=24,
                candidate_ray=j,info_score=info,gradient_score=grad,
                one_ray_defect_gain=dg,one_ray_global_gain=gg,chosen=int(j==1),defect_hit=int(j==0)))
    s,p=summarize(rows)
    assert len(s)==1 and len(p)==2 and s[0]['n_objects']==2
    assert np.isclose(s[0]['info_defect_regret'],0)
    assert np.isclose(s[0]['existing_defect_regret'],.05)
    assert np.isclose(s[0]['info_global_regret'],.01)


def test_bad_pool_rejected():
    rows=[dict(size=12,policy='gradient',object_seed=1,acquired_before=24,
               candidate_ray=j,info_score=float(j),gradient_score=float(j),
               one_ray_defect_gain=.0,one_ray_global_gain=.0,chosen=0,defect_hit=0)
          for j in range(3)]
    with pytest.raises(ValueError):summarize(rows)


def test_no_overwrite_before_dependency_import(tmp_path):
    out=tmp_path/'full';out.mkdir();(out/'keep.txt').write_text('preserve')
    with pytest.raises((FileExistsError,ImportError,ModuleNotFoundError)):
        run(out)
    assert (out/'keep.txt').read_text()=='preserve'
