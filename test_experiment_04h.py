import unittest
import numpy as np
from scipy import sparse
from experiment_04h import stratified_order, voxel_coverage_order, phantom_family, coverage

class Test04H(unittest.TestCase):
    def test_stratified_permutation_and_balancing(self):
        order=stratified_order(4,3,3,42)
        self.assertEqual(len(np.unique(order)),144)
        self.assertTrue(np.array_equal(np.sort(order),np.arange(144)))
        for k in (9,18,45,144):
            counts=np.bincount(order[:k]//16,minlength=9)
            self.assertLessEqual(counts.max()-counts.min(),1)
    def test_greedy_determinism_and_unique(self):
        A=sparse.eye(15,format='csr')
        a=voxel_coverage_order(A,1,5,3,10,7,4)
        b=voxel_coverage_order(A,1,5,3,10,7,4)
        np.testing.assert_array_equal(a,b)
        self.assertEqual(len(set(a)),10)
    def test_coverage_no_measurements(self):
        A=sparse.eye(12,format='csr')
        rec=coverage(A,np.arange(12),2,1,3,6)
        self.assertEqual(rec['covered_voxels'],6)
        self.assertEqual(rec['zero_coverage_voxels'],6)
    def test_phantoms_differ(self):
        p=phantom_family(8)
        self.assertEqual(len(p),4)
        self.assertTrue(all(np.isfinite(x).all() for x in p.values()))
        self.assertFalse(np.array_equal(p['original'],p['shifted']))
if __name__=='__main__':unittest.main()
