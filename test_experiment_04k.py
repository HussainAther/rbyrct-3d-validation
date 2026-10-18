import unittest
import numpy as np
from experiment_04k import new_phantoms, noise_seed_for, paired_per_case
from experiment_04j import adaptive_order
from scipy.sparse import csr_matrix

class Test04K(unittest.TestCase):
    def test_new_shapes(self):
        ph=new_phantoms(12)
        self.assertEqual(set(ph),{'torus','slats','beads','wedges'})
        for v in ph.values():
            self.assertEqual(v.shape,(12,12,12))
            self.assertTrue(np.isfinite(v).all())
        self.assertFalse(np.array_equal(ph['torus'],ph['slats']))
    def test_noise_seed_reproducibility(self):
        self.assertEqual(noise_seed_for(1,'torus',.01),noise_seed_for(1,'torus',.01))
        self.assertNotEqual(noise_seed_for(1,'torus',.01),noise_seed_for(1,'beads',.01))
    def test_paired_gain(self):
        rows=[dict(phantom='torus',seed=1,budget=10,noise_fraction=0.,policy='adaptive_feedback',rmse=.1),
              dict(phantom='torus',seed=1,budget=10,noise_fraction=0.,policy='feedback_off_control',rmse=.2)]
        rec=paired_per_case(rows,'feedback_off_control')
        self.assertEqual(len(rec),1);self.assertAlmostEqual(rec[0]['relative_gain'],.5)
    def test_imported_selector_respects_unobserved_oracle(self):
        rng=np.random.default_rng(3);A=csr_matrix(rng.uniform(.01,1,(48,64)))
        warm=np.arange(8);a=np.ones(48);b=a.copy();b[8:]=30
        x,_,_=adaptive_order(A,a,4,4,warm,12,7,8,4,3,8)
        y,_,_=adaptive_order(A,b,4,4,warm,12,7,8,4,3,8)
        np.testing.assert_array_equal(x,y)

if __name__=='__main__':unittest.main()
