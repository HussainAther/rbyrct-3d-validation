"""Independent AC readiness auditor: checks sources and independently replays AB evidence.

A PASS means the NOT-READY finding is consistent and supported, not that
scientific approvals or 480-job certification exist.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import experiment_08aj_ac as ac
from experiment_08aj_ab_audit import audit as audit_ab

def audit(out,aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir):
    errors=[];counts={}
    try:
        status=ac.check(out,aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir)
        snapshot=ac.load_canonical(Path(out)/'ac_candidate.json')
        for label,root in (('n8',ab8_dir),('n32',ab32_dir)):
            result=audit_ab(root,aa_dir,m_dir)
            counts[label]=result.get('audited_engineering_jobs',0)
            if not result['pass']:errors.append(label+' AB numerical replay failed: '+str(result['errors']))
            if counts[label]!=len(snapshot['engineering_evidence_sha256'][label]):
                errors.append(label+' job count differs from snapshot')
            if label=='n32' and not any(r['job_id']=='information_diag__same' for r in result['details']):
                errors.append('required 32^3 matched diagonal engineering evidence missing')
        if snapshot['remaining_gates']!=[{'gate':i,'title':title,'status':s} for i,title,s in ac.GAPS]:
            errors.append('scientific gate declarations changed')
        if any(snapshot.get(k) is not False for k in ('scientific_signoff','resource_policy_approved','frozen','confirmatory_execution_allowed','production_480_job_executor_implemented','mid_job_resume_implemented','hard_os_memory_limit_implemented')):
            errors.append('unsafe approval or capability flag')
        if snapshot.get('readiness_verdict')!='AC_NOT_READY_FOR_CONFIRMATORY_EXECUTION':
            errors.append('unexpected readiness verdict')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    passed=not errors
    return {'verdict':'AC_INDEPENDENT_READINESS_GAP_AUDIT_PASS' if passed else 'AC_READINESS_AUDIT_FAIL',
            'pass':passed,'errors':errors,'audited_engineering_jobs_by_resolution':counts,
            'blocking_gates':len(ac.GAPS),'production_480_job_certified':False,
            'scientific_signoff':False,'resource_policy_approved':False,'frozen':False,
            'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','aa-dir','m-dir','ab8-dir','ab32-dir','y-dir','z-dir'):
        p.add_argument('--'+name,required=True,type=Path)
    x=p.parse_args();result=audit(x.output_dir,x.aa_dir,x.m_dir,x.ab8_dir,x.ab32_dir,x.y_dir,x.z_dir)
    print(json.dumps(result,indent=2))
    if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
