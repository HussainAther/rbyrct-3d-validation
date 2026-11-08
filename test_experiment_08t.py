import numpy as np
import pytest
from scipy import sparse
from experiment_08t import full_covariance_scores, candidate_pool


def dense_reference(H,Q,tau=1.,sigma=1.):
    a=H.toarray();q=Q.toarray()
    cov=np.linalg.inv(np.eye(a.shape[1])/tau+(a.T@a)/sigma)
    return np.array([(v@cov@cov@v)/(sigma+v@cov@v) for v in q])

@pytest.mark.parametrize('seed',range(4))
def test_woodbury_matches_direct_small(seed):
    rng=np.random.default_rng(seed)
    H=sparse.csr_matrix(rng.normal(size=(3+seed,9)))
    Q=sparse.csr_matrix(rng.normal(size=(5,9)))
    assert np.allclose(full_covariance_scores(H,Q,prior_variance=1.7,observation_variance=.8),dense_reference(H,Q,1.7,.8),rtol=1e-11,atol=1e-12)


def test_empty_history():
    H=sparse.csr_matrix((0,4));Q=sparse.csr_matrix([[1.,0,2,0]])
    score=full_covariance_scores(H,Q,prior_variance=2.,observation_variance=3.)
    assert np.allclose(score,[20/13])


def test_errors():
    H=sparse.csr_matrix((2,4));Q=sparse.csr_matrix((1,3))
    with pytest.raises(ValueError):full_covariance_scores(H,Q)
    with pytest.raises(ValueError):full_covariance_scores(H,sparse.csr_matrix((1,4)),prior_variance=0)
    with pytest.raises(TypeError):full_covariance_scores(np.zeros((2,4)),Q)


def test_candidate_pool_reproducible_and_acquired_excluded():
    A=sparse.csr_matrix((30,9));hist=np.arange(25,dtype=int)
    a,n=candidate_pool(A,hist,7,'coverage',820443,pool=5)
    b,m=candidate_pool(A,hist,7,'coverage',820443,pool=5)
    assert np.array_equal(a,b) and n==m==7 and 7 in a
    assert len(a)==5 and len(np.unique(a))==5 and not set(a)&set(hist[:7])


def test_zero_candidates_scores_are_zero():
    H=sparse.csr_matrix([[1.,0,1.]])
    Q=sparse.csr_matrix([[0.,0,0.],[1.,0,0.]])
    x=full_covariance_scores(H,Q)
    assert x[0]==0 and x[1]>0
