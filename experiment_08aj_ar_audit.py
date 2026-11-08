"""Read-only manifest/identity reconciliation and independent numerical replay via AN auditor."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import experiment_08aj_ar as ar
import experiment_08aj_an_audit as an_audit

def audit(root,aa_dir,m_dir,require_complete=False):
    errors=[];individual=[];replayed=0;group_count=0
    try:
        p=ar.check(root,aa_dir,m_dir)
        engine=Path(root)/'engine'
        checked=an_audit.audit(engine,aa_dir,m_dir,require_complete=require_complete)
        group_count=checked['shared_groups_audited'];replayed=checked['engineering_jobs_audited']
        if not checked['pass']:errors.extend(checked['errors'])
        by_id={x['job_id']:x for x in p['jobs']}
        if len(by_id)!=40:errors.append('missing/duplicate manifest job')
        for d in checked['details']:
            jid=d['job_id']
            if jid not in by_id:errors.append('unmapped numerical evidence: '+jid)
            if not d['pass']:errors.append('independent numerical mismatch: '+jid)
            individual.append({'job_id':jid,'pass':d['pass'],
                 'max_abs_replay_error':d['max_abs_replay_error'],
                 'abs_rmse_difference':d['abs_rmse_difference']})
        if require_complete and replayed!=40:errors.append('complete numerical engineering roster required')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    return {'verdict':'AR_INDEPENDENT_ENGINEERING_MANIFEST_AUDIT_PASS' if not errors else 'AR_ENGINEERING_MANIFEST_AUDIT_FAIL',
         'pass':not errors,'errors':errors,'engineering_groups_audited':group_count,
         'engineering_jobs_numerically_audited':replayed,'details':individual,
         'production_jobs_executed':0,'production_480_job_certified':False,
         'resource_policy_approved':False,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for x in ('output-dir','aa-dir','m-dir'):ap.add_argument('--'+x,required=True,type=Path)
    ap.add_argument('--require-complete',action='store_true')
    a=ap.parse_args();r=audit(a.output_dir,a.aa_dir,a.m_dir,a.require_complete)
    print(json.dumps(r,indent=2))
    if not r['pass']:raise SystemExit(2)
if __name__=='__main__':main()
