"""08AJ-R multi-policy engineering orchestrator. NO prospective execution support.

Wraps the fixed, noncohort 08AJ-Q executor. It cannot select arbitrary phantoms,
prospective seeds, or production execution. Scientific protocol NOT frozen.
"""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import experiment_08aj_q as q

SCHEMA='RBYRCT-08AJ-R-multi-policy-engineering-v1'
JOB_IDS=tuple(f'{p}__{m}' for m in q.MODELS for p in q.POLICIES)
R_SOURCES=('experiment_08aj_r.py','experiment_08aj_r_audit.py')

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')

def init(directory,n=8):
    root=Path(directory)
    if root.exists():raise FileExistsError('refusing to overwrite existing engineering evidence')
    if n not in (8,32):raise ValueError('engineering resolution only')
    p=q.proposal(n)
    root.mkdir(parents=True)
    try:
        q.init(root/'q_jobs',n)
        m={'schema':SCHEMA,'q_plan_sha256':digest(root/'q_jobs'/'engineering_plan.json'),
           'n':n,'budget':p['budget'],'epochs':p['mart_epochs'],
           'engineering_seed':q.SEED,'acquisition_seed':q.ACQ,'noise_seed':q.NOISE,
           'job_ids':list(JOB_IDS),'number_of_jobs':10,
           'execution_allowed':'ENGINEERING_ONLY','confirmatory_execution_allowed':False,
           'frozen':False,'no_confirmatory_outcomes':True,
           'production_480_job_certified':False,
           'source_sha256':{name:digest(Path(__file__).resolve().parent/name) for name in R_SOURCES}}
        q.exclusive(root/'multi_job_plan.json',canonical(m))
    except Exception:
        # Leave directory in place as evidence of failed initialization.
        raise
    return {'verdict':'R_ENGINEERING_PLAN_CREATED','n':n,'planned_engineering_jobs':10,
            'epochs':p['mart_epochs'],'confirmatory_execution_allowed':False,
            'no_confirmatory_outcomes':True}

def check(directory):
    root=Path(directory);blob=(root/'multi_job_plan.json').read_bytes();m=json.loads(blob)
    p,sha=q.check(root/'q_jobs')
    expected={
        'schema':SCHEMA,'q_plan_sha256':sha,'n':p['n'],'budget':p['budget'],'epochs':p['mart_epochs'],
        'engineering_seed':q.SEED,'acquisition_seed':q.ACQ,'noise_seed':q.NOISE,
        'job_ids':list(JOB_IDS),'number_of_jobs':10,
        'execution_allowed':'ENGINEERING_ONLY','confirmatory_execution_allowed':False,
        'frozen':False,'no_confirmatory_outcomes':True,'production_480_job_certified':False,
        'source_sha256':{name:digest(Path(__file__).resolve().parent/name) for name in R_SOURCES}}
    if blob!=canonical(m) or m!=expected:raise ValueError('R_PLAN_SOURCE_OR_GATE_MISMATCH')
    return m,digest(root/'multi_job_plan.json')

def run(directory,policy=None,model=None):
    root=Path(directory);m,h=check(root)
    if (policy is None)!=(model is None):raise ValueError('policy/model must both be specified')
    wanted=JOB_IDS if policy is None else (f'{policy}__{model}',)
    if any(job not in JOB_IDS for job in wanted):raise ValueError('unauthorized engineering job')
    completed=[];reused=[]
    for job in wanted:
        p,mod=job.rsplit('__',1)
        out=q.run_one(root/'q_jobs',p,mod)
        if out['verdict']=='Q_ENGINEERING_JOB_REUSED':reused.append(job)
        elif out['verdict']=='Q_NUMERICAL_ENGINEERING_JOB_PASS':completed.append(job)
        else:raise ValueError('unexpected job verdict')
    return {'verdict':'R_ENGINEERING_JOBS_PASS','new_jobs':completed,'reused_jobs':reused,
            'total_requested':len(wanted),'n':m['n'],'epochs':m['epochs'],
            'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output-dir',required=True,type=Path)
    a.add_argument('--mode',required=True,choices=('init','check','run'))
    a.add_argument('--n',type=int,choices=(8,32),default=8)
    a.add_argument('--policy',choices=q.POLICIES);a.add_argument('--model',choices=q.MODELS)
    opt=a.parse_args()
    if opt.mode=='init':out=init(opt.output_dir,opt.n)
    elif opt.mode=='check':out={'verdict':'R_ENGINEERING_SOURCE_MATCH','plan_sha256':check(opt.output_dir)[1]}
    else:out=run(opt.output_dir,opt.policy,opt.model)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
