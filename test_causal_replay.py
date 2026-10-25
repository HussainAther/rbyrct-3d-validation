"""Targeted deterministic replay of the 04J observation-indexing boundary.

This is a local test, not a proof for every geometry or policy.
"""
import unittest
import numpy as np
from scipy.sparse import csr_matrix
from experiment_04j import adaptive_order


class PrefixReplayOracle:
    def __init__(self, values, reference_order, warm=8, batch=4):
        self.values = values
        self.order = reference_order
        self.acquired = warm
        self.batch = batch
        self.reads = 0

    def __getitem__(self, ids):
        ids = np.asarray(ids, dtype=int)
        expected = self.order[:self.acquired]
        if not np.array_equal(ids, expected):
            raise AssertionError('Read outside the expected acquired prefix')
        self.reads += 1
        self.acquired += self.batch
        return self.values[ids]


class TestCausalReplay(unittest.TestCase):
    def fixture(self, strength):
        rng = np.random.default_rng(123)
        A = csr_matrix(rng.uniform(.01, 1, (48, 64)))
        values = rng.uniform(.2, 2, 48)
        args = (A, values, 4, 4, np.arange(8), 24, 271828)
        kwargs = dict(warm_rays=8, batch=4, provisional_iterations=3,
                      candidate_pool=8, feedback_strength=strength)
        reference, _, _ = adaptive_order(*args, **kwargs)
        return args, kwargs, reference

    def test_reject_deliberate_future_read(self):
        args, _, ref = self.fixture(1.)
        oracle = PrefixReplayOracle(args[1], ref)
        with self.assertRaises(AssertionError):
            oracle[ref[:9]]

    def replay(self, strength):
        args, kwargs, ref = self.fixture(strength)
        oracle = PrefixReplayOracle(args[1], ref)
        order, _, _ = adaptive_order(args[0], oracle, *args[2:], **kwargs)
        np.testing.assert_array_equal(order, ref)
        self.assertEqual(oracle.reads, 4)

    def test_adaptive_feedback_replay(self):
        self.replay(1.)

    def test_feedback_off_replay(self):
        self.replay(0.)


if __name__ == '__main__':
    unittest.main()
