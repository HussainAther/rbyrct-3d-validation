"""Independent 08AJ-AJ audit of live worker termination and numerical recovery."""
import argparse,json
from pathlib import Path
import experiment_08aj_aj as aj
import experiment_08aj_ah as ah
from experiment_08aj_ah_audit import audit as audit_ah


def audit(root,af_dir,aa_dir,m_dir,require_complete=True):
    root=Path(root);errors=[];numerical=None;rows=0
    try:
        p,rows,last=aj.check(root,af_dir,aa_dir,m_dir)
        if not (root/'fault.json').is_file():raise ValueError('missing real-worker failure evidence')
        f=ah.receipt(root/'fault.json')
        if f.get('schema')!=aj.SCHEMA or f.get('verdict')!='AJ_REAL_MART_WORKER_KILLED' or f.get('worker_was_running_at_intervention') is not True or f.get('production_execution_allowed') is not False:
            raise ValueError('invalid fault provenance')
        n=f.get('committed_rows_after_kill');total=f.get('rows_total')
        if not isinstance(n,int) or n<f.get('target_rows',0) or n>=total:raise ValueError('invalid fault checkpoint boundary')
        cp=root/'worker'/'checkpoints'/f'cp_{n:08d}'
        if aj.sha(cp/'receipt.json')!=f.get('checkpoint_receipt_sha256') or aj.sha(cp/'state.npy')!=f.get('checkpoint_state_sha256'):
            raise ValueError('fault checkpoint changed')
        if not (root/'resume.json').exists():
            if require_complete:raise ValueError('recovery not finished')
        else:
            if rows!=total:raise ValueError('recovery missing rows')
            r=ah.receipt(root/'resume.json')
            numerical=audit_ah(root/'worker',af_dir,aa_dir,m_dir)
            if not numerical['pass']:raise ValueError('AH independent numerical replay failed: '+str(numerical['errors']))
            required={'schema':aj.SCHEMA,'verdict':'AJ_REAL_WORKER_RECOVERY_PASS',
                      'rows_done':total,'max_abs_error_vs_af':r.get('max_abs_error_vs_af'),
                      'max_abs_replay_error':numerical['max_abs_replay_error'],
                      'abs_rmse_difference':numerical['abs_rmse_difference'],
                      'fault_receipt_sha256':aj.sha(root/'fault.json'),
                      'final_receipt_sha256':aj.sha(root/'worker'/'final'/'receipt.json'),
                      'production_jobs_executed':0,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
            if not isinstance(r.get('max_abs_error_vs_af'),(float,int)) or abs(r['max_abs_error_vs_af'])>1e-11:
                raise ValueError('AF reference mismatch exceeds tolerance')
            if r!=required:raise ValueError('resume evidence mismatch')
        allowed={'plan.json','worker','fault.json'}|({'resume.json'} if (root/'resume.json').exists() else set())
        if {x.name for x in root.iterdir()}!=allowed:raise ValueError('unexpected AJ artifacts')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    return {'verdict':'AJ_INDEPENDENT_REAL_WORKER_FAILURE_AUDIT_PASS' if not errors else 'AJ_REAL_WORKER_FAILURE_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'rows_audited':rows,
            'max_abs_replay_error':numerical['max_abs_replay_error'] if numerical else None,
            'abs_rmse_difference':numerical['abs_rmse_difference'] if numerical else None,
            'production_jobs_executed':0,'production_480_job_certified':False,
            'resource_policy_approved':False,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','af-dir','aa-dir','m-dir'):ap.add_argument('--'+name,required=True,type=Path)
    ap.add_argument('--allow-incomplete',action='store_true')
    a=ap.parse_args()
    r=audit(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,not a.allow_incomplete)
    print(json.dumps(r,indent=2))
    if not r['pass']:raise SystemExit(2)
if __name__=='__main__':main()
