import unittest
from experiment_04od import summarize_trace,make_audit,matched_object_contrasts

class Test04OD(unittest.TestCase):
    def test_exposure_weighted_by_rays_not_checks(self):
        t=[{'acquired_before':'128','feedback_strength_next':'0','heldout_nrmse':'3'},
           {'acquired_before':'384','feedback_strength_next':'1','heldout_nrmse':'1'}]
        a=summarize_trace(t,1024)
        self.assertEqual(a['controlled_rays'],896)
        self.assertEqual(a['off_rays'],256)
        self.assertEqual(a['on_rays'],640)
        self.assertAlmostEqual(a['on_fraction'],640/896)
        self.assertEqual(a['n_switches'],1)
        self.assertEqual(a['first_on'],384)
    def test_rejects_final_checkpoint(self):
        with self.assertRaises(ValueError):
            summarize_trace([{'acquired_before':'512','feedback_strength_next':'1','heldout_nrmse':'1'}],512)
    def test_rejects_duplicate_checkpoint(self):
        t=[{'acquired_before':'128','feedback_strength_next':'1','heldout_nrmse':'1'}]*2
        with self.assertRaises(ValueError): summarize_trace(t,512)
    def test_missing_policy_is_rejected(self):
        r=dict(object_type='replicated',offset='0',phantom='torus',seed='1',budget='512',noise_fraction='0')
        gate=dict(r,policy='reliability_gate',acquired_before='128',feedback_strength_next='1',heldout_nrmse='1')
        metrics=[dict(r,policy='reliability_gate',rmse='0.1')]
        with self.assertRaises(ValueError): make_audit([gate],metrics)
    def test_matched_object_requires_both(self):
        with self.assertRaises(ValueError):
            matched_object_contrasts([dict(object_type='replicated',offset=0.,phantom='torus',seed=1,budget=512,noise_fraction=0.)])

if __name__=='__main__':unittest.main()
