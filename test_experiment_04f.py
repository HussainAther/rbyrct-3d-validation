import unittest
import numpy as np
from scipy import sparse
from experiment_04f import run_mart, run_sirt, checkpoints_to

class Test04F(unittest.TestCase):
    def test_checkpoints(self):
        self.assertEqual(checkpoints_to(3, [1, 2, 4]), [1, 2, 3])

    def test_both_solvers_identity(self):
        A = sparse.eye(3, format='csr', dtype=np.float64)
        target = np.array([0.1, 0.5, 0.9])
        b = A @ target
        m, mh = run_mart(A, b, target, 30, 0.5, [1, 30])
        s, sh = run_sirt(A, b, target, 2, 1.0, [1, 2])
        self.assertLess(np.max(np.abs(m - target)), 1e-4)
        np.testing.assert_allclose(s, target, atol=1e-12)
        self.assertEqual(len(mh), 2)
        self.assertEqual(len(sh), 2)

    def test_sparse_unobserved_and_empty(self):
        A = sparse.csr_matrix([[1., 0., 0.], [0., 0., 0.]])
        target = np.array([0.5, 0., 0.])
        s, hist = run_sirt(A, A @ target, target, 2, 1.0, [2])
        self.assertTrue(np.isfinite(s).all())
        self.assertAlmostEqual(s[0], 0.5)

    def test_bad_relaxation(self):
        A = sparse.eye(1, format='csr')
        with self.assertRaises(ValueError):
            run_sirt(A, np.ones(1), np.ones(1), 1, 0.0, [1])
        with self.assertRaises(ValueError):
            run_mart(A, np.ones(1), np.ones(1), 1, 2.0, [1])

if __name__ == '__main__':
    unittest.main()
