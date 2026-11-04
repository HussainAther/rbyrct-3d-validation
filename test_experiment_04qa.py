import unittest
import numpy as np
from experiment_04b import system_matrix
from experiment_04qa import march_ray,project,rays,discrepancy

class Test04QA(unittest.TestCase):
    def test_constant_volume_analytic_chord(self):
        vol=np.full((8,8,8),.7)
        for direction in ((1,0,0),(1,1,0),(1,1,1)):
            d=np.asarray(direction,dtype=float);d/=np.linalg.norm(d)
            expected=.7*8/max(abs(x) for x in d)
            self.assertAlmostEqual(march_ray(vol,[0,0,0],d,.35),expected,places=10)
    def test_outside_misses(self):
        self.assertEqual(march_ray(np.ones((8,)*3),[30,0,0],[0,1,0],.2),0.)
    def test_linear_affine_central_ray(self):
        vol=np.zeros((8,8,8),float)
        for x in range(8):vol[:,:,x]=.3+.04*(x-3.5)
        self.assertAlmostEqual(march_ray(vol,[0,0,0],[1,0,0],.1),.3*8,places=10)
    def test_nearest_matches_siddon_limit(self):
        rng=np.random.default_rng(31)
        vol=rng.uniform(size=(6,6,6))
        A=system_matrix(6,3,[0.])
        observed=project(vol,6,3,[0.],step=.01,mode='nearest')
        self.assertLess(discrepancy(observed,A@vol.ravel())['relative_l2'],.005)
    def test_projection_geometry_order(self):
        n=6;angles=3;tilts=[-20.,0.,20.]
        self.assertEqual(len(list(rays(n,angles,tilts))),n*n*angles*len(tilts))
        vol=np.ones((n,)*3)
        A=system_matrix(n,angles,tilts)
        self.assertLess(discrepancy(project(vol,n,angles,tilts,step=.2),A@vol.ravel())['relative_l2'],1e-10)
    def test_invalid_args_and_shape(self):
        with self.assertRaises(ValueError):march_ray(np.ones((6,6,6)),[0,0,0],[1,0,0],0)
        with self.assertRaises(ValueError):project(np.ones((6,6,6)),6,3,[0.],factor=2)
        with self.assertRaises(ValueError):discrepancy(np.ones(2),np.ones(3))
    def test_step_refinement(self):
        rng=np.random.default_rng(812)
        vol=rng.uniform(size=(8,)*3)
        o=np.array([.13,-.27,.23]);d=np.array([1,.73,.27])
        benchmark=march_ray(vol,o,d,.005)
        e1=abs(march_ray(vol,o,d,.5)-benchmark)
        e2=abs(march_ray(vol,o,d,.125)-benchmark)
        self.assertLess(e2,e1)

if __name__=='__main__':unittest.main()
