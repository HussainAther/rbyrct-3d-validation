"""Read-only independent 08AJ-Y register auditor. Never executes or freezes."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from experiment_08aj_y import (EVIDENCE,SCHEMA,CROSSWALK,canonical,read,sha,hashes,evidence_status,decisions,expected_status)

def audit(out,code_root,paths):
 errors=[]
 try:
  root=Path(out);blob=read(root/'scientific_decision_register.json');status_blob=read(root/'run_status.json')
  record=json.loads(blob);status=json.loads(status_blob)
  if blob!=canonical(record):errors.append('register is noncanonical')
  if status_blob!=canonical(status):errors.append('status is noncanonical')
  if record.get('schema')!=SCHEMA:errors.append('schema mismatch')
  if record.get('source_sha256')!=hashes(Path(code_root)):errors.append('source hashes differ')
  if record.get('evidence')!=evidence_status(paths):errors.append('historical review status differs')
  if record.get('gates')!=decisions():errors.append('gate decisions differ')
  if record.get('crosswalk_to_08aj_t_and_x')!={k:list(v) for k,v in CROSSWALK.items()}:errors.append('crosswalk differs')
  if record.get('planned_prospective_jobs')!=480 or record.get('completed_prospective_jobs')!=0:errors.append('prospective count altered')
  for flag in ('frozen','freeze_ready','confirmatory_execution_allowed','scientific_signoff','method_approved','production_480_job_certified'):
   if record.get(flag) is not False:errors.append('unauthorized '+flag)
  if record.get('no_confirmatory_outcomes') is not True:errors.append('confirmatory outcomes flag altered')
  if status!=expected_status(blob):errors.append('status mismatch')
 except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:errors.append(type(exc).__name__+': '+str(exc))
 return {'verdict':'Y_INDEPENDENT_GAP_AUDIT_PASS' if not errors else 'Y_INDEPENDENT_GAP_AUDIT_FAIL',
         'pass':not errors,'errors':errors,'blocking_gates':5,'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--output-dir',type=Path,required=True)
 p.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parent)
 for key in EVIDENCE:p.add_argument('--'+key.lower()+'-dir',type=Path,required=True)
 a=p.parse_args();paths={k:getattr(a,k.lower()+'_dir') for k in EVIDENCE}
 result=audit(a.output_dir,a.code_root,paths)
 print(json.dumps(result,indent=2))
 if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
