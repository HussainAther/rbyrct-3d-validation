import unittest
import numpy as np
from experiment_04ob import auc_score,balanced_accuracy,threshold_for_train,evaluate_group_holdout,scenario_records

class Test04OB(unittest.TestCase):
    def test_auc_perfect(self):
        self.assertAlmostEqual(auc_score([0,1,0,1],[0.1,.8,.2,.9]),1.)
        self.assertAlmostEqual(auc_score([0,1,0,1],[.8,.1,.9,.2]),0.)
    def test_one_class_undefined(self):
        self.assertTrue(np.isnan(auc_score([1,1],[1.,2.])))
    def test_threshold_training_only(self):
        train=[dict(v=v,relative_gain=g) for v,g in [(0.1,.2),(0.2,.3),(.9,-.2),(1.,-.3)]]
        self.assertGreater(threshold_for_train(train,'v'),.2)
        self.assertLess(threshold_for_train(train,'v'),.9)
        self.assertAlmostEqual(balanced_accuracy([0,0,1,1],[0,0,1,1]),1.)
    def test_holdout_prevents_training_on_same_phantom(self):
        rows=[]
        for family in ['a','b','c']:
            for i in range(4):rows.append(dict(phantom=family,budget=512,relative_gain=-1. if i%2 else 1.,v=float(i)))
        r=evaluate_group_holdout(rows,'v')
        self.assertEqual(len(r),3)
        self.assertTrue(all(x['n_train']==8 and x['n_test']==4 for x in r))
    def test_scenario_grouping(self):
        p=[dict(object_type='replicated',offset=0.,phantom='torus',seed=4,budget=b,noise_fraction=0.) for b in [512,1024,2048]]
        _,n=scenario_records(p,[128,256]);self.assertEqual(n,1)
if __name__=='__main__':unittest.main()
