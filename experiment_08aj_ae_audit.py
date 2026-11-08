"""Independent AE dispatcher audit, recomputing every completed AD numerical output."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import experiment_08aj_ae as ae
from experiment_08aj_ad_audit import audit as ad_audit

def audit(out,aa_dir,m_dir,ab_dir,require_complete=False):
    errors=[];details=[];pending=[]
    try:
        p=ae.check(out,aa_dir,m_dir,ab_dir)
        for job in sorted((Path(out)/'jobs').iterdir()):
            num=job/'numerical'
            plan=ae.receipt(num/'plan.json')
            count,_,_=ae.ad.verify_chain(num,plan)
            total=plan['budget']*plan['epochs']
            if count==total and (num/'final.json').is_file():
                result=ad_audit(num,ab_dir,aa_dir,m_dir)
                details.append({'job_id':job.name,'pass':result['pass'],
                       'max_abs_replay_error':result['max_abs_replay_error'],
                       'abs_rmse_difference':result['abs_rmse_difference']})
                if not result['pass']:errors.extend(job.name+': '+x for x in result['errors'])
            else:
                pending.append({'job_id':job.name,'rows_done':count,'rows_total':total})
        if require_complete and pending:errors.append('dispatched engineering jobs incomplete')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    good=not errors
    return {'verdict':'AE_INDEPENDENT_ENGINEERING_DISPATCH_AUDIT_PASS' if good else 'AE_ENGINEERING_DISPATCH_AUDIT_FAIL',
      'pass':good,'errors':errors,'audited_completed_engineering_jobs':len(details),
      'completed_details':details,'pending_engineering_jobs':pending,
      'aa_production_jobs_executed':0,'production_480_job_certified':False,
      'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    for x in ('output-dir','aa-dir','m-dir','ab-dir'):a.add_argument('--'+x,type=Path,required=True)
    a.add_argument('--require-complete',action='store_true')
    x=a.parse_args();r=audit(x.output_dir,x.aa_dir,x.m_dir,x.ab_dir,x.require_complete)
    print(json.dumps(r,indent=2))
    if not r['pass']:raise SystemExit(2)
if __name__=='__main__':main()
