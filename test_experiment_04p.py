import unittest
import numpy as np
from experiment_04p import FAMILIES,POLICIES,phantoms,object_pair,paired_results

class Test04P(unittest.TestCase):
    def test_new_family_shapes_and_finite(self):
        objs=phantoms(12)
        self.assertEqual(set(objs),set(FAMILIES))
        for x in objs.values():
            self.assertEqual(x.shape,(12,12,12));self.assertTrue(np.isfinite(x).all());self.assertGreater(x.std(),0.)
    def test_object_replication(self):
        c,f=object_pair('pores',8,2)['replicated']
        expected=np.repeat(np.repeat(np.repeat(c.reshape(8,8,8),2,axis=0),2,axis=1),2,axis=2)
        np.testing.assert_allclose(f.reshape(16,16,16),expected)
    def test_subvoxel_block_average(self):
        from experiment_04m import downsample_average
        c,f=object_pair('branches',8,2)['subvoxel']
        np.testing.assert_allclose(c,downsample_average(f.reshape(16,16,16),2).ravel())
    def test_new_families_distinct(self):
        objs=phantoms(16)
        for a in FAMILIES:
            for b in FAMILIES:
                if a<b:self.assertGreater(np.max(np.abs(objs[a]-objs[b])),.01)
    def test_pair_reject_incomplete(self):
        rows=[dict(object_type='replicated',offset=0.,phantom='branches',seed=1,budget=128,noise_fraction=0.,policy='adaptive_feedback',rmse=.1)]
        with self.assertRaises(ValueError):paired_results(rows)
    def test_pair_sign(self):
        rows=[dict(object_type='replicated',offset=0.,phantom='branches',seed=1,budget=128,noise_fraction=0.,policy=p,rmse=(.1 if p=='adaptive_feedback' else .2)) for p in POLICIES]
        pairs,summary=paired_results(rows)
        self.assertAlmostEqual(next(r for r in pairs if r['policy']=='adaptive_feedback')['relative_gain'],.5)
        self.assertEqual(len(summary),len(POLICIES)-1)

if __name__=='__main__':unittest.main()
