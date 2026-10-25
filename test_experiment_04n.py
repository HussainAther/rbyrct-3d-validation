import unittest
import numpy as np
from scipy.sparse import csr_matrix
from experiment_04n import replicate_coarse, object_pair, paired_summary, selection_feature_diagnostics

class Test04N(unittest.TestCase):
    def test_exact_replication(self):
        coarse=np.arange(4**3,dtype=float).reshape(4,4,4)
        fine=replicate_coarse(coarse,2)
        from experiment_04m import downsample_average
        np.testing.assert_array_equal(downsample_average(fine,2),coarse)
    def test_replication_and_subvoxel_have_same_dimensions(self):
        obj=object_pair('beads',8,2)
        self.assertEqual(obj['replicated'][0].size,512)
        self.assertEqual(obj['subvoxel'][1].size,4096)
        self.assertTrue(np.all(obj['replicated'][1]>=0))
    def test_paired_gain(self):
        policies=['adaptive_feedback','feedback_off_control','voxel_coverage_greedy','random','geometry_balanced']
        rows=[dict(object_type='replicated',offset=0.,phantom='torus',seed=7,budget=8,noise_fraction=0.,policy=p,rmse=v)
              for p,v in zip(policies,[.1,.2,.3,.4,.5])]
        cases,summary=paired_summary(rows)
        self.assertEqual(len(cases),4)
        self.assertEqual(summary[0]['n'],1)
        self.assertTrue(all(r['win']==1 for r in cases))
    def test_incomplete_case_rejected(self):
        row=dict(object_type='replicated',offset=0.,phantom='torus',seed=7,budget=8,noise_fraction=0.,policy='adaptive_feedback',rmse=.1)
        with self.assertRaises(ValueError):paired_summary([row])
    def test_features_only_acquired_indices(self):
        # Post-hoc prefix audit must never require future measurement values.
        A=csr_matrix(np.eye(64))
        n=4;order=np.arange(32)
        obs=np.ones(64);altered=obs.copy();altered[32:]=999.
        truth=np.ones(64)
        a=selection_feature_diagnostics(A,obs,truth,n,order,8,8,2)
        b=selection_feature_diagnostics(A,altered,truth,n,order,8,8,2)
        self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
