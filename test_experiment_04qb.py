import csv
import tempfile
import unittest
from pathlib import Path
import numpy as np
from experiment_04p import POLICIES,object_pair
from experiment_04qa import project
from experiment_04g import TILTS
from experiment_04b import system_matrix
from experiment_04qb import main,paired_results

class Test04QB(unittest.TestCase):
    def test_independent_projector_not_same_as_coarse_operator(self):
        coarse,fine=object_pair('branches',8,2)['subvoxel']
        observed=project(fine.reshape(16,16,16),8,4,TILTS,2,0.,.5)
        baseline=np.asarray(system_matrix(8,4,TILTS)@coarse).ravel()
        self.assertGreater(np.linalg.norm(observed-baseline),.01)
    def test_replicated_volume_can_still_disagree(self):
        coarse,fine=object_pair('pores',8,2)['replicated']
        observed=project(fine.reshape(16,16,16),8,4,TILTS,2,0.,.5)
        self.assertEqual(len(observed),len(system_matrix(8,4,TILTS)@coarse))
        self.assertTrue(np.isfinite(observed).all())
    def test_paired_table_rejects_missing_policy(self):
        with self.assertRaises(ValueError):
            paired_results([dict(object_type='subvoxel',offset=0,phantom='pores',seed=5,budget=64,noise_fraction=0,policy='adaptive_feedback',rmse=.3)])
    def test_frozen_policy_list(self):
        self.assertEqual(POLICIES,('adaptive_feedback','feedback_off_control','geometry_balanced','voxel_coverage_greedy','reliability_gate'))
    def test_end_to_end_small(self):
        with tempfile.TemporaryDirectory() as td:
            main(['--size','8','--angles','4','--factor','2','--phantoms','branches',
                  '--object-types','replicated','subvoxel','--offsets','0',
                  '--seeds','271828','--budgets','64','--noise-fractions','0',
                  '--warm-rays','16','--batch','8','--provisional-iterations','8',
                  '--diagnostic-iterations','8','--sirt-iterations','12',
                  '--candidate-pool','8','--diagnostic-every','16','--step','0.5',
                  '--output-dir',td])
            with open(Path(td)/'metrics.csv',newline='') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),10)
            self.assertEqual({r['policy'] for r in rows},set(POLICIES))
            with open(Path(td)/'mismatch_diagnostics.csv',newline='') as f:diag=list(csv.DictReader(f))
            self.assertEqual(len(diag),2)
            self.assertTrue(all(float(x['relative_projector_disagreement'])>=0 for x in diag))

if __name__=='__main__': unittest.main()
