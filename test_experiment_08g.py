import numpy as np
import pytest
from scipy.sparse import csr_matrix
from experiment_08g import disagreement_score, _spearman, summarize


def fake_rec(A,y,epochs,relaxation):
    return np.full(A.shape[1],np.mean(y))


def test_score_uses_only_supplied_acquired_measurements():
    A=csr_matrix(np.eye(6)); C=csr_matrix(np.array([[1,1,0,0,0,0],[0,0,0,1,1,0]]))
    score=disagreement_score(A,np.array([1,2,3,6,7,8],dtype=float),C,reconstruct=fake_rec)
    assert score.shape==(2,)
    assert np.isfinite(score).all()
    assert np.allclose(score,5/3)


def test_split_score_is_deterministic():
    A=csr_matrix(np.eye(6));C=A[:3]
    x=disagreement_score(A,np.arange(6,dtype=float),C,reconstruct=fake_rec)
    y=disagreement_score(A,np.arange(6,dtype=float),C,reconstruct=fake_rec)
    assert np.array_equal(x,y)


def test_reject_invalid_histories_and_nonfinite_values():
    A=csr_matrix(np.eye(6)); C=A[:2]
    with pytest.raises(ValueError):disagreement_score(A,np.ones(5),C,reconstruct=fake_rec)
    with pytest.raises(ValueError):disagreement_score(A,[1,2,float('nan'),4,5,6],C,reconstruct=fake_rec)
    with pytest.raises(ValueError):disagreement_score(A,np.ones(6),C,epochs=0,reconstruct=fake_rec)


def test_disagreement_requires_no_candidate_observation_argument():
    A=csr_matrix(np.eye(6));C=A[:2]
    with pytest.raises(TypeError):disagreement_score(A,np.ones(6),C,candidate_observations=np.ones(2),reconstruct=fake_rec)


def test_spearman_and_degenerate():
    assert _spearman([1,2,3],[1,2,3])==pytest.approx(1)
    assert np.isnan(_spearman([1,1,1],[1,2,3]))


def test_object_balanced_summaries():
    rows=[]
    for n in (12,32):
      for policy in ('gradient','incremental_25'):
        for obj in (1,2):
          for k in range(2):
            for j in range(4):
              rows.append(dict(size=n,policy=policy,object_seed=obj,acquired_before=k+4,
                candidate_ray=j,gradient_score=float(j),disagreement_score=float(3-j),
                one_ray_global_gain=.001*j,one_ray_defect_gain=.01*j,
                defect_hit=int(j==3),chosen=int(j==3)))
    out=summarize(rows)
    assert len(out)==4
    assert all(x['n_objects']==2 and x['n_pools']==4 for x in out)
    assert all(x['disagreement_defect_regret']>0 for x in out)
