import unittest
import numpy as np
from scipy.sparse import csr_matrix
from experiment_04o import acquired_only_reliability,pair,attach_signals

class GuardedOracle:
    def __init__(self,values,allowed):self.values=np.asarray(values);self.allowed=set(allowed)
    def __getitem__(self,ids):
        ids=np.asarray(ids).ravel()
        if not set(map(int,ids)).issubset(self.allowed):raise AssertionError('unacquired oracle access')
        return self.values[ids]

class Test04O(unittest.TestCase):
    def test_no_unacquired_measurements(self):
        A=csr_matrix(np.eye(64,8))
        observed=GuardedOracle(np.arange(64,dtype=float),range(24))
        sig=acquired_only_reliability(A,observed,np.arange(24),2,2,.25)
        self.assertEqual(sig['n_holdout'],6)
    def test_reliability_repeatable(self):
        A=csr_matrix(np.tile(np.eye(8),(6,1)))
        b=np.arange(48,dtype=float)
        a=acquired_only_reliability(A,b,np.arange(32),2,3,.2,seed=17)
        c=acquired_only_reliability(A,b,np.arange(32),2,3,.2,seed=17)
        self.assertEqual(a,c)
    def test_pairing(self):
        meta=dict(object_type='replicated',offset=0.,phantom='torus',seed=1,budget=64,noise_fraction=0.)
        q=pair([dict(**meta,policy='adaptive_feedback',rmse=.1),dict(**meta,policy='feedback_off_control',rmse=.2)])
        self.assertAlmostEqual(q[0]['relative_gain'],.5)
    def test_incomplete_case_rejected(self):
        with self.assertRaises(ValueError):pair([dict(object_type='replicated',offset=0,phantom='torus',seed=1,budget=64,noise_fraction=0,policy='adaptive_feedback',rmse=.2)])
    def test_signal_requires_matching_case(self):
        p=[dict(object_type='replicated',offset=0,phantom='torus',seed=1,budget=64,noise_fraction=0,relative_gain=.1,adaptive_win=1,adaptive_rmse=.1,off_rmse=.2)]
        with self.assertRaises(ValueError):attach_signals(p,[])
if __name__=='__main__':unittest.main()
