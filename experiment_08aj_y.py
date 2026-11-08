"""08AJ-Y scientific decision consolidation. Review only: cannot freeze or execute."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path

SCHEMA='RBYRCT-08AJ-Y-scientific-gaps-v1'
SOURCE_FILES=('experiment_08aj_t.py','experiment_08aj_u.py','experiment_08aj_v.py','experiment_08aj_w.py','experiment_08aj_x.py')
EVIDENCE={
 'T':('T_FREEZE_READINESS_REVIEW_REQUIRED','candidate_sha256','b3bfb59d5031a37945197da4e167c6bcec328e0cd1fdc4973339f099e64255d7'),
 'U':('SCIENTIFIC_REVIEW_EVIDENCE_PREPARED',None,None),
 'V':('V_STATISTICAL_CALIBRATION_EVIDENCE_PREPARED','calibration_sha256','139d13ba72d5a4aa3df74dd4efc79ef528f2fb85029518a9b4f463637c085f58'),
 'W':('W_STATISTICAL_METHOD_REVIEW_PREPARED','review_sha256','6d50397ac98b54448d88d3a32f5c97b9a09a920f1845df71c88873e2d7c71cfd'),
 'X':('X_ESTIMAND_REVIEW_PREPARED','review_sha256','3b4ebab093d4753d67f4bd1ca395080ea700c3de7ab1ed429aeee58329c298a0'),
}
CROSSWALK={
 'G1':('T-01','X01','X02','X04'),
 'G2':('T-02','X03','X05'),
 'G3':('T-03','X05'),
 'G4':('T-04','X06'),
 'G5':('T-05','X07'),
}

def canonical(value):
 return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode()
def sha(blob):return hashlib.sha256(blob).hexdigest()
def read(path):
 p=Path(path)
 if p.is_symlink() or not p.is_file():raise FileNotFoundError('missing or unsafe: '+str(p))
 return p.read_bytes()
def hashes(code_root):return {n:sha(read(code_root/n)) for n in SOURCE_FILES}
def evidence_status(paths):
 out={}
 for tag,(verdict,field,expected) in EVIDENCE.items():
  root=Path(paths[tag]);blob=read(root/'run_status.json');record=json.loads(blob)
  if record.get('verdict')!=verdict:raise ValueError(tag+' unexpected review verdict')
  if record.get('frozen') is not False or record.get('no_confirmatory_outcomes') is not True:raise ValueError(tag+' unsafe review flags')
  if record.get('confirmatory_execution_allowed',False) is not False:raise ValueError(tag+' execution is unlocked')
  if record.get('scientific_signoff',False) is not False or record.get('method_approved',False) is not False:raise ValueError(tag+' unauthorized scientific approval')
  if field and record.get(field)!=expected:raise ValueError(tag+' review fingerprint unexpected')
  out[tag]={'status_sha256':sha(blob),'verdict':verdict,'fingerprint_field':field,'fingerprint':record.get(field) if field else None,
            'path_display':tag+' original review directory (external; not included in Y archive)'}
 return out

def decisions():
 return [
 {'gate':'G1','title':'Phantom scope and independence','status':'REVIEW_REQUIRED','evidence':'08AJ-U morphology review; 08AJ-X fixed synthetic families',
  'recommended_decision':'Primary claim restricted to 24 fixed synthetic objects, with three related stress-test families. Do not claim independent real-world populations.',
  'needs':'Named scientific reviewer confirms generator comparison, benchmark framing and limits. Generator-level inference separately justified if requested.'},
 {'gate':'G2','title':'Primary estimand and inferential interpretation','status':'REVIEW_REQUIRED','evidence':'08AJ-V and W calibration; 08AJ-X estimand review',
  'recommended_decision':'Primary descriptive arithmetic mean of 24 object-level gains. Optional conditional generator-level stratified Welch-t with bootstrap-t sensitivity only if sampling assumptions approved.',
  'needs':'Prespecify reported families, dispersion, all object gains, practical effect benchmark, inference assumptions and treatment of multiplicity.'},
 {'gate':'G3','title':'Resource ceilings and failure handling','status':'UNAPPROVED','evidence':'32^3 engineering audits in 08AJ-I, N, Q, R; 08AJ-H draft ceilings',
  'recommended_decision':'Never impute missing or invalid jobs; preserve failures; no outcome-dependent retry, tuning or stopping.',
  'needs':'Approve peak-memory and per-job/total time ceilings, failure taxonomy, deterministic retry limits, and stop/go rules before execution.'},
 {'gate':'G4','title':'Full production executor and independent outcome audit','status':'NOT_IMPLEMENTED_OR_CERTIFIED','evidence':'08AJ-R ten noncohort jobs and 08AJ-M/O disabled 480-job contract',
  'recommended_decision':'Keep all confirmatory execution disabled.',
  'needs':'Implement and audit all 480 production jobs, per-object truth and RMSE checks, paired-noise/ordering checks, recovery and outcome integrity on noncohort fixtures.'},
 {'gate':'G5','title':'Source freeze and accountable scientific sign-off','status':'NOT_AUTHORIZED','evidence':'08AJ-T freeze gate and 08AJ-X unsigned decision recommendations',
  'recommended_decision':'Do not freeze, unlock or run the confirmatory cohort.',
  'needs':'Named scientific sign-off, engineering sign-off, version-control commit/tag and dependency lock, independently audited locked manifest and separate explicit execute authorization.'},
 ]

def record(code_root,paths):
 return {'schema':SCHEMA,'stage':'08AJ-Y','review_only':True,'frozen':False,'freeze_ready':False,'confirmatory_execution_allowed':False,
         'scientific_signoff':False,'method_approved':False,'production_480_job_certified':False,'no_confirmatory_outcomes':True,
         'source_sha256':hashes(code_root),'evidence':evidence_status(paths),'gates':decisions(),
         'crosswalk_to_08aj_t_and_x':{k:list(v) for k,v in CROSSWALK.items()},
         'planned_prospective_jobs':480,'completed_prospective_jobs':0,
         'scope':{'n':32,'budget_rays':2048,'mart_epochs':16,'fixed_objects':24,'families':3,'acquisition_seeds':2,'models':2,'policies':5},
         'minimum_next_actions':['Obtain accountable approval of benchmark scope and prespecified descriptive/inferential claims',
             'Approve quantitative resource ceilings and deterministic failure policy',
             'Implement the actual 480-job runner with independent truth/RMSE and outcome audit on noncohort test fixtures',
             'Produce a frozen commit/tag and versioned dependency manifest only after review; separately authorize actual study'],
         'caution':'Passing this review audit does not certify production, independent synthetic draws, inference or manuscript claims.'}

def expected_status(blob):
 return {'verdict':'Y_GAP_REGISTER_PREPARED','decision_gates':5,'blocking_gates':5,'register_sha256':sha(blob),
         'frozen':False,'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True,'scientific_signoff':False}
def prepare(out,code_root,paths):
 out=Path(out)
 if out.exists():raise FileExistsError('refusing to overwrite scientific review evidence')
 b=canonical(record(Path(code_root),paths));s=canonical(expected_status(b));out.mkdir(parents=True)
 for name,blob in (('scientific_decision_register.json',b),('run_status.json',s)):
  with (out/name).open('xb') as f:
   f.write(blob);f.flush();os.fsync(f.fileno())
 return json.loads(s)
def check(out,code_root,paths):
 out=Path(out);b=read(out/'scientific_decision_register.json');s=read(out/'run_status.json')
 if b!=canonical(json.loads(b)) or b!=canonical(record(Path(code_root),paths)):raise ValueError('decision register or sources/evidence changed')
 if s!=canonical(expected_status(b)):raise ValueError('status or execution gate changed')
 return {'verdict':'Y_SOURCES_AND_DECISIONS_MATCH','blocking_gates':5,'register_sha256':sha(b),'confirmatory_execution_allowed':False}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--mode',choices=('prepare','check','freeze','run'),required=True)
 p.add_argument('--output-dir',type=Path,required=True)
 p.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parent)
 for key in EVIDENCE:p.add_argument('--'+key.lower()+'-dir',type=Path,required=True)
 a=p.parse_args()
 if a.mode in ('freeze','run'):p.error('FREEZE_BLOCKED: scientific approvals and full production certification missing')
 paths={k:getattr(a,k.lower()+'_dir') for k in EVIDENCE}
 result=prepare(a.output_dir,a.code_root,paths) if a.mode=='prepare' else check(a.output_dir,a.code_root,paths)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
