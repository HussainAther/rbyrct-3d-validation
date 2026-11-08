import json
import numpy as np
import pytest
from experiment_08aj_w import sample,calibration,decision,report,main
from experiment_08aj_w_audit import audit

def test_sample_fixed_shapes():
 x=sample(np.random.default_rng(1),'normal_equal',.02,.03,0)
 assert x.shape==(3,8) and np.isfinite(x).all()

def test_invalid_rho():
 with pytest.raises(ValueError):sample(np.random.default_rng(1),'normal_equal',0,.03,1)

def test_default_disabled():
 d=report(trials=100,bootstraps=200)
 assert not d['method_approved'] and not d['confirmatory_execution_allowed'] and len(d['rows'])==192

def test_method_recommendation_conditional():
 d=report(trials=100,bootstraps=200)
 assert d['decision']['status']=='CONDITIONAL_RECOMMENDATION_NOT_APPROVED'
 assert d['decision']['provisional_primary_method']=='stratified_welch_t'

def test_dependency_sensitivity_present():
 d=report(trials=100,bootstraps=200)
 assert len(d['decision']['within_family_dependence_sensitivity'])==2

def test_real_artifact_audit(tmp_path):
 root=tmp_path/'review';main(['--output-dir',str(root),'--trials','100','--bootstraps','200'])
 assert audit(root)['pass']

def test_tamper_detected(tmp_path):
 root=tmp_path/'review';main(['--output-dir',str(root),'--trials','100','--bootstraps','200'])
 p=root/'statistical_method_review.json';p.write_bytes(p.read_bytes()+b' ')
 assert not audit(root)['pass']

def test_no_overwrite(tmp_path):
 root=tmp_path/'review';main(['--output-dir',str(root),'--trials','100','--bootstraps','200'])
 with pytest.raises(FileExistsError):main(['--output-dir',str(root),'--trials','100','--bootstraps','200'])
