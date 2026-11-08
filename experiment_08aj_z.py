"""08AJ-Z: resource/failure controls for real NONCOHORT engineering jobs.

The 480-job M contract remains strictly disabled. No execution mode accepts
prospective object IDs, seeds, production authorizations, or unfreezes.
"""
from __future__ import annotations
import argparse, hashlib, json, os, time
from pathlib import Path
import numpy as np
import experiment_08aj_m as m
import experiment_08aj_r as r
import experiment_08aj_q as q
from experiment_08aj_e import full_resolution_pair

SCHEMA='RBYRCT-08AJ-Z-engineering-resource-gate-v1'
SOURCES=('experiment_08aj_z.py','experiment_08aj_z_audit.py')
# PROPOSED, NOT SIGNED OFF. Resource gates are engineering limits only.
POLICY={'job_wall_seconds':600.0,'total_wall_seconds':7200.0,
        'process_peak_bytes':8*1024**3,'max_retries_for_failed_jobs':0,
        'missing_outcome':'abort_no_imputation','invalid_numerics':'abort_preserve_artifacts',
        'source_drift':'abort','stop_on_resource_exceedance':True,
        'no_outcome_driven_stopping':True,'approval':'PROPOSED_NOT_APPROVED'}

def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
def sha(b):return hashlib.sha256(b).hexdigest()
def code_hashes():
    root=Path(__file__).resolve().parent
    return {name:sha((root/name).read_bytes()) for name in SOURCES}
def rss_peak():
    try:
        import psutil
        proc=psutil.Process()
        if os.name=='nt':
            return int(proc.memory_info().peak_wset)
        import resource
        v=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(v if __import__('sys').platform=='darwin' else v*1024)
    except (ImportError,AttributeError):return None

def prepare(output_dir,m_dir,n=8):
    root=Path(output_dir)
    if root.exists():raise FileExistsError('will not overwrite existing Z evidence')
    if n not in (8,32):raise ValueError('only 8^3/32^3 engineering sizes are authorized')
    _,mh=m.check(m_dir)
    root.mkdir(parents=True)
    r.init(root/'engineering',n)
    proposal={'schema':SCHEMA,'m_contract_sha256':mh,
       'm_roster_sha256':sha((Path(m_dir)/'jobs.json').read_bytes()),
       'm_job_count':480,'m_contract_execution_allowed':False,
       'engineering_job_ids':list(r.JOB_IDS),'engineering_n':n,
       'resource_failure_policy':POLICY,'source_sha256':code_hashes(),
       'scientific_signoff':False,'frozen':False,
       'confirmatory_execution_allowed':False,'production_480_job_certified':False,
       'no_confirmatory_outcomes':True}
    q.exclusive(root/'z_plan.json',canonical(proposal))
    (root/'diagnostics').mkdir()
    (root/'failures').mkdir()
    return {'verdict':'Z_ENGINEERING_GATE_PREPARED','engineering_jobs':10,
            'production_jobs':480,'production_execution_allowed':False,
            'resource_policy_approved':False,'no_confirmatory_outcomes':True}

def check(root,m_dir):
    root=Path(root)
    blob=(root/'z_plan.json').read_bytes();p=json.loads(blob)
    _,mh=m.check(m_dir)
    expected={'schema':SCHEMA,'m_contract_sha256':mh,
      'm_roster_sha256':sha((Path(m_dir)/'jobs.json').read_bytes()),
      'm_job_count':480,'m_contract_execution_allowed':False,
      'engineering_job_ids':list(r.JOB_IDS),'engineering_n':p.get('engineering_n'),
      'resource_failure_policy':POLICY,'source_sha256':code_hashes(),
      'scientific_signoff':False,'frozen':False,
      'confirmatory_execution_allowed':False,'production_480_job_certified':False,
      'no_confirmatory_outcomes':True}
    if p.get('engineering_n') not in (8,32) or blob!=canonical(p) or p!=expected:
        raise ValueError('Z_PLAN_SOURCE_OR_EXECUTION_GATE_MISMATCH')
    rp,_=r.check(root/'engineering')
    if rp['n']!=p['engineering_n']:raise ValueError('engineering size mismatch')
    for name in ('diagnostics','failures'):
        if not (root/name).is_dir() or (root/name).is_symlink():raise ValueError('missing/unsafe '+name)
    return p,sha(blob)

def write_failure(root,job,kind,details):
    # Never replace a prior failure; require a new destination on retries.
    path=Path(root)/'failures'/(job+'.json')
    payload={'schema':SCHEMA,'job_id':job,'failure_kind':kind,'details':str(details),
             'no_confirmatory_outcomes':True,'retry_allowed':False}
    q.exclusive(path,canonical(payload))

def audit_and_record_one(root,policy,model):
    from experiment_08aj_q_audit import audit_one
    job=f'{policy}__{model}';folder=Path(root)/'engineering'/'q_jobs'/'jobs'/job
    d=audit_one(Path(root)/'engineering'/'q_jobs',policy,model)
    if not d['pass']:raise ValueError('independent numerical audit failed: '+str(d['errors']))
    plan=json.loads((Path(root)/'engineering'/'q_jobs'/'engineering_plan.json').read_bytes())
    truth,_=full_resolution_pair(q.FAMILY,q.SEED,plan['n'])
    recon=np.load(folder/'reconstruction.npy',allow_pickle=False)
    rmse=float(np.sqrt(np.mean((recon-truth)**2)))
    if not np.isfinite(rmse) or rmse<0:raise ValueError('invalid engineering RMSE')
    rec={'schema':SCHEMA,'job_id':job,'engineering_only':True,
         'q_receipt_sha256':sha((folder/'receipt.json').read_bytes()),
         'truth_sha256':sha(np.asarray(truth,dtype='<f8').tobytes()),
         'reconstruction_sha256':sha((folder/'reconstruction.npy').read_bytes()),
         'rmse':rmse,'replay_max_abs_error':d['max_abs_replay_error'],
         'no_confirmatory_outcomes':True}
    file=Path(root)/'diagnostics'/(job+'.json')
    if file.exists():
        if file.read_bytes()!=canonical(rec):raise ValueError('existing diagnostic changed')
    else:q.exclusive(file,canonical(rec))
    return rec

def run(root,m_dir,policy=None,model=None):
    root=Path(root);p,_=check(root,m_dir)
    if (policy is None)!=(model is None):raise ValueError('specify both policy and model')
    wanted=list(r.JOB_IDS) if policy is None else [f'{policy}__{model}']
    if any(job not in r.JOB_IDS for job in wanted):raise ValueError('unauthorized job')
    before=time.perf_counter();new=[];reused=[]
    # Absolute ceilings apply per invocation; existing receipts are retained.
    for job in wanted:
        if (root/'failures'/(job+'.json')).exists():raise ValueError('prior failure preserved; no automatic retry: '+job)
        if time.perf_counter()-before>POLICY['total_wall_seconds']:
            write_failure(root,job,'TOTAL_WALL_CEILING','invocation wall clock exhausted')
            raise RuntimeError('total wall ceiling exceeded')
        pp,mod=job.rsplit('__',1)
        started=time.perf_counter()
        try:
            result=r.run(root/'engineering',pp,mod)
            elapsed=time.perf_counter()-started
            actual=(root/'engineering'/'q_jobs'/'jobs'/job/'receipt.json')
            job_rec=json.loads(actual.read_bytes())
            # The Q receipt measures its own numerical execution; use it for the per-job ceiling.
            if job_rec['elapsed_seconds']>POLICY['job_wall_seconds']:
                raise RuntimeError('job wall ceiling exceeded')
            peak=rss_peak()
            if peak is not None and peak>POLICY['process_peak_bytes']:
                raise RuntimeError('process peak memory ceiling exceeded')
            audit_and_record_one(root,pp,mod)
            (new if result['new_jobs'] else reused).append(job)
        except Exception as exc:
            write_failure(root,job,type(exc).__name__,str(exc))
            raise
    return {'verdict':'Z_ENGINEERING_EXECUTION_PASS','new_jobs':new,'reused_jobs':reused,
            'jobs_requested':len(wanted),'resource_policy_approved':False,
            'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--m-dir',required=True,type=Path)
    ap.add_argument('--mode',required=True,choices=('prepare','check','run','freeze','production-run'))
    ap.add_argument('--n',type=int,choices=(8,32),default=8)
    ap.add_argument('--policy');ap.add_argument('--model')
    args=ap.parse_args()
    if args.mode in ('freeze','production-run'):raise RuntimeError('PRODUCTION_DISABLED_UNTIL_SCIENTIFIC_SIGNOFF_AND_SOURCE_LOCK')
    if args.mode=='prepare':out=prepare(args.output_dir,args.m_dir,args.n)
    elif args.mode=='check':out={'verdict':'Z_SOURCE_AND_GATE_MATCH','plan_sha256':check(args.output_dir,args.m_dir)[1]}
    else:out=run(args.output_dir,args.m_dir,args.policy,args.model)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
