"""08AJ-Q engineering-only per-policy numerical executor; NOT a 480-job production runner.

Only a fixed noncohort object is permitted. No production, freeze, prospective seed,
or arbitrary phantom override exists. Results are not comparative scientific outcomes.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_d import SEEDS, POLICIES
from experiment_08aj_e import full_resolution_pair, model_measurements, checked_mart
from experiment_08aj_g import fair_orders

SCHEMA='RBYRCT-08AJ-Q-engineering-per-job-v1'
SEED=970099
FAMILY='smooth_heterogeneity'
ACQ=940411
NOISE=970119
MODELS=('same','independent')
ARTIFACTS=('order.npy','measurements.npy','clean_catalogue.npy','noisy_catalogue.npy','csr_data.npy','csr_indices.npy','csr_indptr.npy','reconstruction.npy')
SOURCES=('experiment_04b.py','experiment_04g.py','experiment_04h.py','experiment_04qa.py','experiment_05b_08b.py','experiment_05b_mart.py','experiment_08aj_b.py','experiment_08aj_c_view.py','experiment_08aj_d.py','experiment_08aj_e.py','experiment_08aj_f.py','experiment_08aj_g.py','experiment_08aj_q.py','experiment_08aj_q_audit.py','experiment_08j.py','experiment_08k.py')

def canonical(a): return (json.dumps(a,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
def sha(b): return hashlib.sha256(b).hexdigest()
def exclusive(path,data):
    with Path(path).open('xb') as f: f.write(data);f.flush();os.fsync(f.fileno())
def save(path,data):
    with Path(path).open('xb') as f:np.save(f,data,allow_pickle=False);f.flush();os.fsync(f.fileno())
def proposal(n=8):
    if n not in (8,32):raise ValueError('engineering sizes only')
    if SEED in {s for group in SEEDS.values() for s in group}:raise RuntimeError('engineering cohort seed collision')
    root=Path(__file__).resolve().parent
    return {'schema':SCHEMA,'mode':'ENGINEERING_ONLY','engineering_seed':SEED,'family':FAMILY,
            'acquisition_seed':ACQ,'noise_seed':NOISE,'n':n,'angles':4,
            'budget':128 if n==8 else 2048,'warm':8 if n==8 else 64,
            'pool':16,'batch':8 if n==8 else 32,'mart_epochs':2 if n==8 else 16,
            'relaxation':.25,'noise_fraction':.005,
            'models':list(MODELS),'policies':list(POLICIES),
            'frozen':False,'execution_allowed':False,'confirmatory_execution_allowed':False,
            'no_confirmatory_outcomes':True,'production_480_job_certified':False,
            'source_sha256':{f:sha((root/f).read_bytes()) for f in SOURCES}}
def init(root,n=8):
    root=Path(root)
    if root.exists():raise FileExistsError('will not overwrite existing evidence')
    p=proposal(n);root.mkdir(parents=True)
    exclusive(root/'engineering_plan.json',canonical(p));(root/'jobs').mkdir()
    return {'verdict':'Q_ENGINEERING_PLAN_CREATED','n':n,'jobs_enabled':'ENGINEERING_ONLY','no_confirmatory_outcomes':True}
def check(root):
    root=Path(root);blob=(root/'engineering_plan.json').read_bytes();p=json.loads(blob)
    if blob!=canonical(p) or p!=proposal(p['n']):raise ValueError('ENGINEERING_SOURCE_OR_PLAN_MISMATCH')
    allowed={f'{policy}__{model}' for policy in POLICIES for model in MODELS}
    present={f.name for f in (root/'jobs').iterdir()}
    if any(x not in allowed and not x.startswith('.staging__') for x in present):raise ValueError('unexpected job directory')
    return p,sha(blob)
def run_one(root,policy,model,*,interrupt_after_commit=False):
    from experiment_08aj_q_audit import audit_one
    root=Path(root);p,plan_sha=check(root)
    if policy not in POLICIES or model not in MODELS:raise ValueError('unauthorized engineering job')
    job=f'{policy}__{model}';target=root/'jobs'/job
    if target.exists():
        result=audit_one(root,policy,model)
        if not result['pass']:raise ValueError('committed evidence rejected: '+str(result['errors']))
        return {'verdict':'Q_ENGINEERING_JOB_REUSED','job_id':job,'replay_error':result['max_abs_replay_error'],'no_confirmatory_outcomes':True}
    stage=root/'jobs'/('.staging__'+job)
    if stage.exists():
        # Uncommitted partial evidence can never be silently treated as completed.
        shutil.rmtree(stage)
    stage.mkdir()
    t=time.perf_counter()
    try:
        A=system_matrix(p['n'],4,TILTS).tocsr()
        orders,prefix=fair_orders(A,n=p['n'],angles=4,seed=ACQ,budget=p['budget'],warm=p['warm'],pool=p['pool'],batch=p['batch'])
        order=np.asarray(orders[policy],dtype=np.int64)
        truth,fine=full_resolution_pair(FAMILY,SEED,p['n'])
        clean,noisy=model_measurements(A,truth,fine,n=p['n'],angles=4,model=model,noise_seed=NOISE,noise_fraction=.005)
        selected=A[order].tocsr()
        reconstruction=checked_mart(A,noisy,order,epochs=p['mart_epochs'],relaxation=.25)
        data={'order.npy':order,'measurements.npy':noisy[order],'clean_catalogue.npy':clean,
              'noisy_catalogue.npy':noisy,'csr_data.npy':selected.data,'csr_indices.npy':selected.indices,
              'csr_indptr.npy':selected.indptr,'reconstruction.npy':reconstruction}
        if set(data)!=set(ARTIFACTS) or any(not np.isfinite(v).all() for v in data.values()):raise ValueError('invalid arrays')
        for name in ARTIFACTS:save(stage/name,data[name])
        receipt={'schema':SCHEMA,'job_id':job,'policy':policy,'model':model,
                 'plan_sha256':plan_sha,'n':p['n'],'budget':p['budget'],'epochs':p['mart_epochs'],
                 'engineering_only':True,'no_confirmatory_outcomes':True,
                 'elapsed_seconds':time.perf_counter()-t,
                 'artifact_sha256':{name:sha((stage/name).read_bytes()) for name in ARTIFACTS}}
        exclusive(stage/'receipt.json',canonical(receipt));stage.rename(target)
    except Exception:
        # Persist partial staging evidence for diagnosis; next run can discard it.
        raise
    if interrupt_after_commit:raise RuntimeError('SIMULATED_INTERRUPTION_AFTER_COMMIT '+job)
    return {'verdict':'Q_NUMERICAL_ENGINEERING_JOB_PASS','job_id':job,
            'n':p['n'],'epochs':p['mart_epochs'],'no_confirmatory_outcomes':True,
            'production_480_job_certified':False}
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--mode',required=True,choices=('init','check','run'))
    ap.add_argument('--n',type=int,choices=(8,32),default=8)
    ap.add_argument('--policy',choices=POLICIES)
    ap.add_argument('--model',choices=MODELS)
    a=ap.parse_args()
    if a.mode=='init':res=init(a.output_dir,a.n)
    elif a.mode=='check':res={'verdict':'Q_ENGINEERING_SOURCE_MATCH','plan_sha256':check(a.output_dir)[1]}
    else:
        if not a.policy or not a.model:ap.error('run requires --policy and --model')
        res=run_one(a.output_dir,a.policy,a.model)
    print(json.dumps(res,indent=2))
if __name__=='__main__':main()
