import unittest
import numpy as np
from scipy import sparse
from experiment_04i import heldout_phantoms, noisy_full_projection, paired_summary
from experiment_04h import voxel_coverage_order

class Test04I(unittest.TestCase):
    def test_phantoms_new_and_finite(self):
        p=heldout_phantoms(8)
        self.assertEqual(set(p),{'shell','cross','bands','ribbon'})
        for value in p.values():
            self.assertEqual(value.shape,(8,8,8))
            self.assertTrue(np.isfinite(value).all())
        self.assertGreater(np.linalg.norm(p['cross']-p['bands']),.1)

    def test_noise_reproducible_and_zero(self):
        clean=np.array([2.,4.,1.,3.])
        np.testing.assert_array_equal(noisy_full_projection(clean,0,17),clean)
        np.testing.assert_array_equal(noisy_full_projection(clean,.01,17),noisy_full_projection(clean,.01,17))
        self.assertFalse(np.array_equal(noisy_full_projection(clean,.01,17),noisy_full_projection(clean,.01,18)))
        with self.assertRaises(ValueError):noisy_full_projection(clean,-.1,17)

    def test_paired_win_definition(self):
        records=[dict(phantom='a',seed=1,budget=8,noise_fraction=0.,policy=k,rmse=v)
                 for k,v in [('random',.2),('voxel_coverage_greedy',.1)]]
        result=paired_summary(records)
        self.assertEqual(result[0]['wins'],1)
        self.assertAlmostEqual(result[0]['mean_relative_rmse_gain'],.5)

    def test_greedy_unique_fixed_seed(self):
        A=sparse.eye(12,format='csr')
        a=voxel_coverage_order(A,2,3,1,5,7,4)
        b=voxel_coverage_order(A,2,3,1,5,7,4)
        np.testing.assert_array_equal(a,b)
        self.assertEqual(len(set(a)),5)

if __name__=='__main__':unittest.main()
