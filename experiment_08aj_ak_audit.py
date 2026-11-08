"""Independent aggregate AK multi-job engineering audit; no prospective execution."""
import argparse,json
from pathlib import Path
import experiment_08aj_ak as ak
from experiment_08aj_ah_audit import audit as ah_audit

def audit(root,af_dir,aa_dir,m_dir,require_complete=False):
    errors=[];details=[];complete=0
    try:
        r=ak.check(root,af_dir,aa_dir,m_dir)
        for entry in r['entries']:
            jid=entry['job_id'];d=Path(root)/'jobs'/jid
            if not d.exists():
                if require_complete:errors.append('not dispatched: '+jid)
                continue
            if not (d/'worker'/'final').exists():
                if require_complete:errors.append('incomplete: '+jid)
                continue
            x=ah_audit(d/'worker',af_dir,aa_dir,m_dir)
            details.append({'job_id':jid,'pass':x['pass'],'errors':x['errors'],
                            'max_abs_replay_error':x['max_abs_replay_error'],
                            'abs_rmse_difference':x['abs_rmse_difference']})
            if x['pass']:complete+=1
            else:errors.extend(jid+': '+str(y) for y in x['errors'])
        if require_complete and complete!=4:errors.append('four completed engineering shadows required')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    return {'verdict':'AK_INDEPENDENT_MULTI_JOB_ENGINEERING_AUDIT_PASS' if not errors else 'AK_INDEPENDENT_MULTI_JOB_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'audited_completed_engineering_jobs':complete,
            'details':details,'production_jobs_executed':0,'production_480_job_certified':False,
            'resource_policy_approved':False,'production_execution_allowed':False,
            'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('output-dir','af-dir','aa-dir','m-dir'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--require-complete',action='store_true');a=p.parse_args()
    x=audit(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.require_complete)
    print(json.dumps(x,indent=2))
    if not x['pass']:raise SystemExit(2)
if __name__=='__main__':main()
