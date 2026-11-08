import json
from pathlib import Path
import pytest
from experiment_08aj_y import EVIDENCE,SOURCE_FILES,canonical,prepare,check
from experiment_08aj_y_audit import audit

def fixture(tmp):
 code=tmp/'code';code.mkdir()
 for name in SOURCE_FILES:(code/name).write_text('fixture '+name)
 paths={}
 for key,(verdict,field,value) in EVIDENCE.items():
  p=tmp/key;p.mkdir();r={'verdict':verdict,'frozen':False,'no_confirmatory_outcomes':True,'confirmatory_execution_allowed':False}
  if field:r[field]=value
  (p/'run_status.json').write_bytes(canonical(r));paths[key]=p
 return code,paths,tmp/'out'

def test_prepare(tmp_path):
 c,p,o=fixture(tmp_path);r=prepare(o,c,p)
 assert r['blocking_gates']==5 and not r['frozen']
def test_source_check(tmp_path):
 c,p,o=fixture(tmp_path);prepare(o,c,p)
 assert check(o,c,p)['verdict']=='Y_SOURCES_AND_DECISIONS_MATCH'
def test_independent_audit(tmp_path):
 c,p,o=fixture(tmp_path);prepare(o,c,p)
 assert audit(o,c,p)['pass']
def test_overwrite_protected(tmp_path):
 c,p,o=fixture(tmp_path);prepare(o,c,p)
 with pytest.raises(FileExistsError):prepare(o,c,p)
def test_source_change_rejected(tmp_path):
 c,p,o=fixture(tmp_path);prepare(o,c,p);(c/SOURCE_FILES[0]).write_text('changed')
 with pytest.raises(ValueError):check(o,c,p)
 assert not audit(o,c,p)['pass']
def test_prior_evidence_change_rejected(tmp_path):
 c,p,o=fixture(tmp_path);prepare(o,c,p)
 r=json.loads((p['W']/'run_status.json').read_text());r['method_approved']=True
 (p['W']/'run_status.json').write_bytes(canonical(r))
 assert not audit(o,c,p)['pass']
def test_no_unauthorized_unlock(tmp_path):
 c,p,o=fixture(tmp_path);prepare(o,c,p)
 r=json.loads((o/'scientific_decision_register.json').read_text());r['confirmatory_execution_allowed']=True
 (o/'scientific_decision_register.json').write_bytes(canonical(r))
 assert not audit(o,c,p)['pass']
def test_decision_scoping(tmp_path):
 c,p,o=fixture(tmp_path);prepare(o,c,p)
 r=json.loads((o/'scientific_decision_register.json').read_text())
 assert len(r['gates'])==5
 assert r['completed_prospective_jobs']==0
 assert 'Fixed' not in r['gates'][1]['recommended_decision']
 assert '24 object' in r['gates'][1]['recommended_decision']
