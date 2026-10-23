import unittest
import numpy as np
from scipy.sparse import csr_matrix
from experiment_04oc import AcquiredOnly,online_order,paired_table
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04j import adaptive_order

class Test04OC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n=4;cls.angles=2
        cls.A=system_matrix(cls.n,cls.angles,TILTS).tocsr()
        cls.observed=np.asarray(cls.A@np.linspace(.1,.9,cls.n**3)).ravel()
        cls.fixed=voxel_coverage_order(cls.A,cls.n,cls.angles,len(TILTS),64,11,8)
        cls.options=dict(warm_rays=16,batch=8,provisional_iterations=3,diagnostic_iterations=3,candidate_pool=8,diagnostic_every=8)
    def test_oracle_restricts_future(self):
        x=AcquiredOnly(np.arange(8));x.commit([1,2]);np.testing.assert_array_equal(x[[1,2]],[1,2])
        with self.assertRaises(AssertionError):x[[1,7]]
    def test_exact_frozen_feedback_and_off(self):
        for policy,strength in [('adaptive_feedback',1.),('feedback_off_control',0.)]:
            ids,_,_=online_order(self.A,self.observed,self.n,self.angles,self.fixed,48,11,policy=policy,**self.options)
            frozen,_,_=adaptive_order(self.A,self.observed,self.n,self.angles,self.fixed,48,11,16,8,3,8,strength)
            np.testing.assert_array_equal(ids,frozen)
    def test_repeatable_gate(self):
        kw=dict(policy='reliability_gate',threshold=1.5,**self.options)
        a,tr,_=online_order(self.A,self.observed,self.n,self.angles,self.fixed,48,11,**kw)
        b,br,_=online_order(self.A,self.observed,self.n,self.angles,self.fixed,48,11,**kw)
        np.testing.assert_array_equal(a,b);self.assertEqual(tr,br)
        self.assertTrue(all(t['acquired_before']<48 for t in tr))
    def test_no_future_observation_changes_early_decisions(self):
        kw=dict(policy='reliability_gate',threshold=2.,**self.options)
        shorter,_,_=online_order(self.A,self.observed,self.n,self.angles,self.fixed,32,11,**kw)
        # Guarded source is the primary leakage guarantee; prefix consistency is also verified.
        longer,_,_=online_order(self.A,self.observed,self.n,self.angles,self.fixed,48,11,**kw)
        np.testing.assert_array_equal(shorter,longer[:32])
    def test_pairing_rejects_incomplete(self):
        with self.assertRaises(ValueError):paired_table([dict(object_type='replicated',offset=0.,phantom='torus',seed=1,budget=32,noise_fraction=0.,policy='adaptive_feedback',rmse=.1)])

if __name__=='__main__':unittest.main()
