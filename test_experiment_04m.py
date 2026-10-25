import unittest
import numpy as np
from experiment_04m import high_resolution_matrix, downsample_average, paired_cases
from experiment_04b import system_matrix
from experiment_04g import TILTS

class Test04M(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n=4;cls.angles=2
        cls.A=system_matrix(cls.n,cls.angles,TILTS)
        cls.H=high_resolution_matrix(cls.n,cls.angles,TILTS,2)
    def test_shapes_and_nonnegativity(self):
        self.assertEqual(self.H.shape,(self.A.shape[0],(self.n*2)**3))
        self.assertTrue(np.all(self.H.data>=0))
    def test_uniform_phantom_integrals_agree(self):
        np.testing.assert_allclose(self.H@np.ones((self.n*2)**3), self.A@np.ones(self.n**3),atol=1e-9)
    def test_forward_mismatch_is_real(self):
        fine=np.zeros((8,8,8));fine[2:6,3:5,1:4]=1.
        coarse=downsample_average(fine,2)
        self.assertGreater(float(np.linalg.norm(self.H@fine.ravel()-self.A@coarse.ravel())),1e-3)
    def test_geometry_offset_changes_operator(self):
        perturbed=high_resolution_matrix(self.n,self.angles,TILTS,2,0.18)
        obj=np.zeros((8,8,8));obj[2:5,3:6,3:6]=1.
        self.assertGreater(float(np.linalg.norm((perturbed-self.H)@obj.ravel())),1e-3)
    def test_pairing_and_unique_cases(self):
        rows=[dict(stage='fine',phantom='a',seed=1,budget=40,noise_fraction=0,policy=k,rmse=v) for k,v in [('adaptive_feedback',0.2),('feedback_off_control',0.3)]]
        self.assertEqual(paired_cases(rows,'feedback_off_control')[0]['win'],1)
        with self.assertRaises(ValueError):paired_cases(rows+[rows[0]],'feedback_off_control')
if __name__=='__main__':unittest.main()
