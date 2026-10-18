import unittest
import numpy as np
from scipy import sparse
from experiment_04g import policies, low_frequency_basis, geometry_ig_order, acquire

class Test04G(unittest.TestCase):
    def test_policies_permutations_and_prefixes(self):
        p=policies(4,3,3,104729)
        for order in p.values():
            self.assertEqual(len(order),144)
            np.testing.assert_array_equal(np.sort(order),np.arange(144))
            self.assertEqual(len(np.unique(order[:40])),40)

    def test_geometry_only_ig_deterministic(self):
        rng=np.random.default_rng(2)
        A=sparse.random(32,8,density=.5,random_state=3,format='csr');A.data=np.abs(A.data)
        B=rng.normal(size=(8,3))
        x=geometry_ig_order(A,B,12,batch=3)
        y=geometry_ig_order(A,B,12,batch=3)
        np.testing.assert_array_equal(x,y)
        self.assertEqual(len(set(x.tolist())),12)

    def test_basis_orthonormal(self):
        B=low_frequency_basis(4,2)
        np.testing.assert_allclose(B.T@B,np.eye(8),atol=1e-12)

    def test_acquisition_uses_selected_measurements(self):
        A=sparse.eye(4,format='csr')
        truth=np.array([1.,2.,3.,4.]);b=A@truth
        order=np.array([3,1,0,2])
        x1,_=acquire(A,b,truth,order,2,3,1.0)
        b2=b.copy();b2[0]+=10;b2[2]+=20
        x2,_=acquire(A,b2,truth,order,2,3,1.0)
        np.testing.assert_array_equal(x1,x2)

if __name__=='__main__': unittest.main()
