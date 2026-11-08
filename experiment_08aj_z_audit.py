"""Independent 08AJ-Z engineering diagnostic and resource-policy auditor.

Reads Z/M/R/Q evidence and recomputes engineering RMSE against the fixed
noncohort truth. No access to prospective outcomes or authorization path.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import experiment_08aj_m as m
from experiment_08aj_e import full_resolution_pair
from experiment_08aj_q_audit import audit_one
from experiment_08aj_r_audit import audit as audit_r

SCHEMA='RBYRCT-08AJ-Z-engineering-resource-gate-v1'
JOB_IDS=tuple(f'{p}__{model}' for model in ('same','independent') for p in ('information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view'))
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')

def audit(root,m_dir,require_complete=False):
    errors=[];details=[];root=Path(root)
    try:
        blob=(root/'z_plan.json').read_bytes();plan=json.loads(blob)
        if blob!=canonical(plan) or plan.get('schema')!=SCHEMA or plan.get('scientific_signoff') is not False or plan.get('frozen') is not False or plan.get('confirmatory_execution_allowed') is not False or plan.get('production_480_job_certified') is not False or plan.get('no_confirmatory_outcomes') is not True or plan.get('m_contract_execution_allowed') is not False or plan.get('m_job_count')!=480:
            errors.append('invalid execution-disabled plan')
        _,mh=m.check(m_dir)
        if plan.get('m_contract_sha256')!=mh or plan.get('m_roster_sha256')!=sha((Path(m_dir)/'jobs.json').read_bytes()):errors.append('M source or roster mismatch')
        if plan.get('engineering_job_ids')!=list(JOB_IDS):errors.append('engineering roster mismatch')
        if plan.get('resource_failure_policy',{}).get('approval')!='PROPOSED_NOT_APPROVED':errors.append('resource approval incorrectly asserted')
        for name,h in plan.get('source_sha256',{}).items():
            source=Path(__file__).resolve().parent/name
            if name not in ('experiment_08aj_z.py','experiment_08aj_z_audit.py') or not source.exists() or sha(source.read_bytes())!=h:errors.append('Z source mismatch '+name)
        if set(plan.get('source_sha256',{}))!={'experiment_08aj_z.py','experiment_08aj_z_audit.py'}:errors.append('Z source roster invalid')
        root_r=root/'engineering';root_q=root_r/'q_jobs'
        rres=audit_r(root_r,require_complete=require_complete)
        if not rres['pass']:errors.extend('R '+e for e in rres['errors'])
        jobdir=root_q/'jobs';present={f.name for f in jobdir.iterdir() if not f.name.startswith('.staging__')}
        if any(f.name.startswith('.staging__') for f in jobdir.iterdir()):errors.append('uncommitted staging artifacts')
        diagnostics=root/'diagnostics';reports={f.stem for f in diagnostics.iterdir() if f.suffix=='.json'}
        if reports!=present:errors.append('diagnostic receipt roster differs from numerical jobs')
        if any(x not in JOB_IDS for x in present):errors.append('unexpected numerical job')
        if any(f.name not in {x+'.json' for x in JOB_IDS} for f in diagnostics.iterdir()):errors.append('unexpected diagnostic file')
        if any(root.joinpath('failures').iterdir()):errors.append('preserved failure artifacts require review')
        n=plan.get('engineering_n');truth,_=full_resolution_pair('smooth_heterogeneity',970099,n)
        truth_hash=sha(np.asarray(truth,dtype='<f8').tobytes())
        for job in sorted(present.intersection(JOB_IDS)):
            policy,model=job.rsplit('__',1)
            qres=audit_one(root_q,policy,model)
            if not qres['pass']:errors.extend('Q '+job+' '+s for s in qres['errors']);continue
            f=diagnostics/(job+'.json');b=f.read_bytes();rec=json.loads(b)
            saved=(jobdir/job/'reconstruction.npy')
            recon=np.load(saved,allow_pickle=False)
            rmse=float(np.sqrt(np.mean((recon-truth)**2)))
            receipt=jobdir/job/'receipt.json'
            if b!=canonical(rec) or rec.get('schema')!=SCHEMA or rec.get('job_id')!=job or rec.get('engineering_only') is not True or rec.get('no_confirmatory_outcomes') is not True or rec.get('truth_sha256')!=truth_hash or rec.get('q_receipt_sha256')!=sha(receipt.read_bytes()) or rec.get('reconstruction_sha256')!=sha(saved.read_bytes()) or not np.isclose(rec.get('rmse',np.nan),rmse,atol=1e-13,rtol=1e-12) or rec.get('replay_max_abs_error')!=qres['max_abs_replay_error']:
                errors.append('diagnostic RMSE/integrity mismatch '+job)
            qreceipt=json.loads(receipt.read_bytes());resource=plan['resource_failure_policy']
            if qreceipt['elapsed_seconds']>resource['job_wall_seconds']:errors.append('wall time gate exceeded '+job)
            details.append({'job_id':job,'pass':True,'rmse_recomputed':True,'replay_error':qres['max_abs_replay_error']})
        if require_complete and len(present)!=10:errors.append('full ten engineering jobs required')
    except Exception as ex:errors.append(type(ex).__name__+': '+str(ex))
    return {'verdict':'Z_INDEPENDENT_ENGINEERING_AUDIT_PASS' if not errors else 'Z_INDEPENDENT_ENGINEERING_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'audited_engineering_jobs':len(details),
            'require_complete':bool(require_complete),'resource_policy_approved':False,
            'confirmatory_execution_allowed':False,'production_480_job_certified':False,
            'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path);ap.add_argument('--m-dir',required=True,type=Path)
    ap.add_argument('--require-complete',action='store_true');a=ap.parse_args()
    result=audit(a.output_dir,a.m_dir,a.require_complete)
    print(json.dumps(result,indent=2))
    if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
