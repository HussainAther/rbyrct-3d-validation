import unittest
import tempfile
from pathlib import Path
from experiment_04l import pairwise, audit_existing, write_rows

class Test04L(unittest.TestCase):
    def test_pairwise_math(self):
        a=[dict(phantom='beads',seed=1,budget=512,noise_fraction=0,policy='adaptive_feedback',rmse=.12),
           dict(phantom='beads',seed=1,budget=512,noise_fraction=0,policy='feedback_off_control',rmse=.10)]
        p=pairwise(a)[0]
        self.assertAlmostEqual(p['relative_gain'],-.2)
        self.assertEqual(p['win'],0)
    def test_iteration_groups_do_not_mix(self):
        records=[]
        for it in [20,40]:
            for method,rmse in [('adaptive_feedback',0.1),('feedback_off_control',0.2)]:
                records.append(dict(phantom='torus',seed=1,budget=64,noise_fraction=0,
                    sirt_iterations=it,policy=method,rmse=rmse))
        self.assertEqual(len(pairwise(records)),2)
    def test_duplicate_case_guard(self):
        row=dict(phantom='beads',seed=1,budget=64,noise_fraction=0,policy='adaptive_feedback',rmse=0.1)
        with self.assertRaises(ValueError):pairwise([row,row])
    def test_audit_negative_cases(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);source=path/'source';source.mkdir()
            write_rows(source/'metrics.csv',[
                dict(phantom='beads',seed=1,budget=512,noise_fraction=0,policy='adaptive_feedback',rmse=.13),
                dict(phantom='beads',seed=1,budget=512,noise_fraction=0,policy='feedback_off_control',rmse=.1)])
            report=audit_existing(source,path/'out')
            self.assertEqual(report['negative_cases'],1)
            self.assertTrue((path/'out'/'negative_cases.csv').exists())

if __name__=='__main__':unittest.main()
