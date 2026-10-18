import unittest
import numpy as np
from scipy.sparse import csr_matrix
from experiment_04j import sirt_silent, image_score, adaptive_order, divergence

class Test04J(unittest.TestCase):
    def test_sirt_identity(self):
        A=csr_matrix(np.eye(8));truth=np.arange(8,dtype=float)/9
        np.testing.assert_allclose(sirt_silent(A,truth,2),truth,atol=1e-12)
    def test_features_respond_to_data(self):
        x=np.ones(4**3); y=x.copy();y[10]=4
        self.assertGreater(float(np.std(image_score(y,4))),float(np.std(image_score(x,4))))
    def test_no_future_measurement_leakage(self):
        # All acquired measurements fixed, unacquired 'oracle' data altered.
        rng=np.random.default_rng(18); A=csr_matrix(rng.uniform(0.01,1,(48,64)))
        warm=np.arange(8);obs=np.ones(48); other=obs.copy();other[8:]=rng.normal(size=40)*100
        a,_,_=adaptive_order(A,obs,4,4,warm,12,13,8,4,3,8)
        b,_,_=adaptive_order(A,other,4,4,warm,12,13,8,4,3,8)
        np.testing.assert_array_equal(a,b)
    def test_unique_and_prefix(self):
        rng=np.random.default_rng(20);A=csr_matrix(rng.uniform(0,1,(48,64)))
        out,trace,_=adaptive_order(A,np.ones(48),4,4,np.arange(8),20,12,8,3,2,8)
        self.assertEqual(len(out),20);self.assertEqual(len(set(out)),20)
        np.testing.assert_array_equal(out[:8],np.arange(8))
        self.assertEqual(trace[-1]['acquired'],20)
    def test_divergence(self):
        self.assertTrue(divergence([0,1,2],[0,1,2])['sequence_identical'])
        self.assertFalse(divergence([0,1,2],[0,2,1])['sequence_identical'])

if __name__=='__main__':unittest.main()
